"""Grant, use, revoke, use again."""

import base64
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from consent.models import ConsentGrant
from idp.models import RevokedToken

from .conftest import FIRST_PARTY, bearer, get_token, login

pytestmark = pytest.mark.django_db

def create_grant(api, session, client, context="gaming", scope=None):
    body = {"client_id": client.client_id, "persona_context": context}
    if scope:
        body["scope"] = scope
    response = api.post("/api/v1/consents", body, format="json", **bearer(session, FIRST_PARTY))
    assert response.status_code in (200, 201)
    return response.json()["id"]

def read(api, user, token, context="gaming"):
    return api.get(f"/api/v1/users/{user.id}/personas/{context}", **bearer(token))

def test_grant_use_revoke_use_again(api, user, client_app):
    session = login(api, user)
    grant_id = create_grant(api, session, client_app[0])
    token = get_token(api, client_app, user, "read:profile:gaming")
    assert read(api, user, token).status_code == 200
    assert api.delete(f"/api/v1/consents/{grant_id}", **bearer(session, FIRST_PARTY)).status_code == 204
    response = read(api, user, token)
    assert response.status_code == 403 and response.json()["detail"] == "no active consent"

def test_regrant_restores_access_with_new_row(api, user, client_app):
    session = login(api, user)
    first = create_grant(api, session, client_app[0])
    api.delete(f"/api/v1/consents/{first}", **bearer(session, FIRST_PARTY))
    second = create_grant(api, session, client_app[0])
    assert first != second
    token = get_token(api, client_app, user, "read:profile:gaming")
    assert read(api, user, token).status_code == 200

def test_revoked_grant_is_kept_for_audit(api, user, client_app):
    session = login(api, user)
    grant_id = create_grant(api, session, client_app[0])
    api.delete(f"/api/v1/consents/{grant_id}", **bearer(session, FIRST_PARTY))
    assert ConsentGrant.objects.get(id=grant_id).revoked_at is not None

def test_revoking_one_grant_leaves_others(api, user, client_app):
    session = login(api, user)
    gaming = create_grant(api, session, client_app[0], "gaming")
    create_grant(api, session, client_app[0], "personal")
    api.delete(f"/api/v1/consents/{gaming}", **bearer(session, FIRST_PARTY))
    token = get_token(api, client_app, user, "read:profile:personal")
    assert read(api, user, token, "personal").status_code == 200

def test_deleting_twice_is_idempotent(api, user, client_app):
    session = login(api, user)
    grant_id = create_grant(api, session, client_app[0])
    assert api.delete(f"/api/v1/consents/{grant_id}", **bearer(session, FIRST_PARTY)).status_code == 204
    assert api.delete(f"/api/v1/consents/{grant_id}", **bearer(session, FIRST_PARTY)).status_code == 204

def test_token_revocation_blocks_even_with_active_consent(api, user, client_app):
    session = login(api, user)
    create_grant(api, session, client_app[0])
    token = get_token(api, client_app, user, "read:profile:gaming")
    client, secret = client_app
    api.post("/api/v1/oauth/revoke", {"token": token}, HTTP_AUTHORIZATION="Basic " + base64.b64encode(f"{client.client_id}:{secret}".encode()).decode())
    assert read(api, user, token).status_code == 401

def test_write_grant_then_downgrade_to_read(api, user, client_app):
    session = login(api, user)
    create_grant(api, session, client_app[0], scope="read:profile:gaming write:profile:gaming")
    token = get_token(api, client_app, user, "write:profile:gaming")
    body = {"attributes": [{"attribute_key": "favourite_game", "attribute_value": "Chess"}]}
    url = f"/api/v1/users/{user.id}/personas/gaming"
    assert api.patch(url, body, format="json", **bearer(token)).status_code == 200
    create_grant(api, session, client_app[0], scope="read:profile:gaming")
    assert api.patch(url, body, format="json", **bearer(token)).status_code == 403

def test_purge_command_removes_only_expired_rows(db):
    now = timezone.now()
    RevokedToken.objects.create(jti="old", expires_at=now - timedelta(hours=1))
    RevokedToken.objects.create(jti="live", expires_at=now + timedelta(hours=1))
    call_command("purge_revoked_tokens")
    assert list(RevokedToken.objects.values_list("jti", flat=True)) == ["live"]