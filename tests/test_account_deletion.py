"""DELETE /api/v1/users/{id}: account erasure by the owner (Table 3, Chapter III H)."""

import pytest

from accounts.models import User
from clients.models import ApiClient
from consent.models import ConsentGrant
from gateway.models import AccessLog
from idp.models import RevokedToken
from personas.models import ContextualName, Persona, PersonaAttribute

from .conftest import FIRST_PARTY, bearer, get_token, grant, login

pytestmark = pytest.mark.django_db

def delete_account(api, user, token, origin=FIRST_PARTY):
    return api.delete(f"/api/v1/users/{user.id}", **bearer(token, origin))

def test_owner_deletes_account(api, user):
    session = login(api, user)
    response = delete_account(api, user, session)
    assert response.status_code == 204
    assert not User.objects.filter(id=user.id).exists()

def test_deletion_removes_all_identity_data(api, user, other_user, client_app):
    grant(user, client_app[0], "gaming")
    session = login(api, user)
    assert delete_account(api, user, session).status_code == 204
    assert not Persona.objects.filter(user_id=user.id).exists()
    assert not PersonaAttribute.objects.filter(persona__user_id=user.id).exists()
    assert not ContextualName.objects.filter(user_id=user.id).exists()
    assert not ConsentGrant.objects.filter(user_id=user.id).exists()
    assert not ApiClient.objects.filter(owner_id=user.id).exists()

def test_other_accounts_are_untouched(api, user, other_user):
    session = login(api, user)
    delete_account(api, user, session)
    assert User.objects.filter(id=other_user.id).exists()
    assert Persona.objects.filter(user_id=other_user.id).count() == 3
    assert ContextualName.objects.filter(user_id=other_user.id).count() == 3

def test_session_token_is_revoked(api, user):
    session = login(api, user)
    delete_account(api, user, session)
    assert RevokedToken.objects.count() == 1
    response = api.get("/api/v1/consents", **bearer(session, FIRST_PARTY))
    assert response.status_code == 401 and response.json()["detail"] == "token revoked"

def test_second_session_is_refused(api, user):
    first = login(api, user)
    second = login(api, user)
    delete_account(api, user, first)
    response = api.get(f"/api/v1/users/{user.id}/personas", **bearer(second, FIRST_PARTY))
    assert response.status_code == 401 and response.json()["detail"] == "account deleted"
    response = api.get("/api/v1/consents", **bearer(second, FIRST_PARTY))
    assert response.status_code == 401 and response.json()["detail"] == "account deleted"

def test_refresh_cookie_stops_working(api, user):
    session = login(api, user)  # sets the refresh cookie on the test client
    delete_account(api, user, session)
    response = api.post("/api/v1/auth/refresh", HTTP_ORIGIN=FIRST_PARTY)
    assert response.status_code == 401

def test_client_token_loses_access(api, user, other_user, client_app):
    grant(other_user, client_app[0], "gaming")
    token = get_token(api, client_app, other_user, "read:profile:gaming")
    session = login(api, other_user)
    assert delete_account(api, other_user, session).status_code == 204
    response = api.get(f"/api/v1/users/{other_user.id}/personas/gaming", **bearer(token))
    assert response.status_code == 403 and response.json()["detail"] == "no active consent"

def test_not_signed_in(api, user):
    response = api.delete(f"/api/v1/users/{user.id}", HTTP_ORIGIN=FIRST_PARTY)
    assert response.status_code == 401
    assert User.objects.filter(id=user.id).exists()

def test_not_the_account_owner(api, user, other_user):
    session = login(api, other_user)
    response = delete_account(api, user, session)
    assert response.status_code == 403 and response.json()["detail"] == "not the account owner"
    assert User.objects.filter(id=user.id).exists()

def test_client_token_cannot_delete(api, user, client_app):
    grant(user, client_app[0], "gaming", "read:profile:gaming write:profile:gaming")
    token = get_token(api, client_app, user, "write:profile:gaming")
    response = api.delete(f"/api/v1/users/{user.id}", **bearer(token))
    assert response.status_code == 403 and response.json()["detail"] == "session token required"
    assert User.objects.filter(id=user.id).exists()

def test_foreign_origin_is_refused(api, user):
    session = login(api, user)
    response = delete_account(api, user, session, origin="https://evil.example")
    assert response.status_code == 403
    assert User.objects.filter(id=user.id).exists()

def test_deletion_is_audited(api, user):
    session = login(api, user)
    delete_account(api, user, session)
    row = AccessLog.objects.filter(endpoint=f"/api/v1/users/{user.id}").latest("id")
    assert (row.method, row.decision, row.reason, row.status_code) == ("DELETE", "allow", "account deleted", 204)
