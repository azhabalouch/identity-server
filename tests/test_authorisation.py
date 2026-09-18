"""Authorisation failures: a valid token without the right permission returns 403."""

import pytest

from clients.models import ApiClient

from .conftest import FIRST_PARTY, bearer, get_token, grant, login

pytestmark = pytest.mark.django_db

@pytest.fixture
def gaming_token(api, user, client_app):
    grant(user, client_app[0], "gaming")
    return get_token(api, client_app, user, "read:profile:gaming")

def url(user, context="gaming"):
    return f"/api/v1/users/{user.id}/personas/{context}"

def test_unregistered_origin_returns_403(api, user, gaming_token):
    response = api.get(url(user), **bearer(gaming_token, "https://evil.example"))
    assert response.status_code == 403
    assert response.json()["detail"] == "origin not registered"

def test_missing_origin_returns_403(api, user, gaming_token):
    assert api.get(url(user), **bearer(gaming_token, None)).status_code == 403

def test_origin_of_a_different_registered_client_returns_403(api, user, gaming_token):
    ApiClient.register(user.id, "Other", "https://other.example")
    assert api.get(url(user), **bearer(gaming_token, "https://other.example")).status_code == 403

def test_no_consent_returns_403(api, user, client_app):
    token = get_token(api, client_app, user, "read:profile:gaming")
    response = api.get(url(user), **bearer(token))
    assert response.status_code == 403
    assert response.json()["detail"] == "no active consent"

def test_scope_mismatch_returns_403(api, user, client_app, gaming_token):
    grant(user, client_app[0], "professional")  # consent exists, but the token is still gaming-scoped
    response = api.get(url(user, "professional"), **bearer(gaming_token))
    assert response.status_code == 403
    assert response.json()["detail"] == "scope mismatch"

def test_read_consent_does_not_allow_write(api, user, client_app):
    grant(user, client_app[0], "gaming")  # read only
    token = get_token(api, client_app, user, "write:profile:gaming")
    response = api.patch(url(user), {"attributes": [{"attribute_key": "gamertag", "attribute_value": "X"}]}, format="json", **bearer(token))
    assert response.status_code == 403

def test_read_token_cannot_patch_even_with_write_consent(api, user, client_app):
    grant(user, client_app[0], "gaming", "read:profile:gaming write:profile:gaming")
    token = get_token(api, client_app, user, "read:profile:gaming")
    response = api.patch(url(user), {"attributes": [{"attribute_key": "gamertag", "attribute_value": "X"}]}, format="json", **bearer(token))
    assert response.status_code == 403

def test_wildcard_without_any_consent_returns_403(api, user, client_app):
    token = get_token(api, client_app, user, "read:profile:*")
    assert api.get(f"/api/v1/users/{user.id}/personas", **bearer(token)).status_code == 403

def test_single_scope_token_cannot_use_wildcard_list(api, user, gaming_token):
    assert api.get(f"/api/v1/users/{user.id}/personas", **bearer(gaming_token)).status_code == 403

def test_client_token_cannot_use_session_routes(api, gaming_token):
    response = api.get("/api/v1/consents", **bearer(gaming_token))
    assert response.status_code == 403
    assert response.json()["detail"] == "session token required"

def test_client_token_cannot_add_names(api, user, gaming_token):
    response = api.post(f"/api/v1/users/{user.id}/names",
                        {"name_value": "X", "name_type": "nickname", "context": "gaming"},
                        format="json", **bearer(gaming_token))
    assert response.status_code == 403

def test_session_from_foreign_origin_returns_403(api, user):
    token = login(api, user)
    assert api.get("/api/v1/consents", **bearer(token, "https://evil.example")).status_code == 403

def test_login_from_foreign_origin_returns_403(api, user):
    response = api.post("/api/v1/auth/login", {"email": user.email, "password": "x" * 12}, format="json", HTTP_ORIGIN="https://evil.example")
    assert response.status_code == 403

def test_deleting_another_users_grant_returns_403(api, user, other_user, client_app):
    theirs = grant(other_user, client_app[0], "gaming")
    token = login(api, user)
    response = api.delete(f"/api/v1/consents/{theirs.id}", **bearer(token, FIRST_PARTY))
    assert response.status_code == 403
    theirs.refresh_from_db()
    assert theirs.revoked_at is None