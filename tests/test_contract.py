"""Endpoint contract: every route returns its documented status code and payload shape."""

import base64

import pytest

from clients.models import ApiClient
from consent.models import ConsentGrant

from .conftest import CLIENT_ORIGIN, FIRST_PARTY, PASSWORD, bearer, get_token, grant, login

pytestmark = pytest.mark.django_db

def basic(client, secret):
    return {"HTTP_AUTHORIZATION": "Basic " + base64.b64encode(f"{client.client_id}:{secret}".encode()).decode()}

# ---------------------------------------------------------------- registration
def test_register_returns_201_and_creates_three_personas(api):
    response = api.post("/api/v1/users", {"email": "New@Example.com", "password": PASSWORD}, format="json")
    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"
    from personas.models import Persona
    assert Persona.objects.filter(user_id=response.json()["id"]).count() == 3

def test_register_duplicate_email_returns_409(api, user):
    response = api.post("/api/v1/users", {"email": user.email, "password": PASSWORD}, format="json")
    assert response.status_code == 409

@pytest.mark.parametrize("payload", [
    {"email": "not-an-email", "password": PASSWORD},
    {"email": "a@example.com", "password": "short"},
    {"email": "a@example.com"},
])

def test_register_invalid_payload_returns_400(api, payload):
    assert api.post("/api/v1/users", payload, format="json").status_code == 400

def test_register_rejects_unexpected_fields(api):
    response = api.post("/api/v1/users", {"email": "x@example.com", "password": PASSWORD, "is_active": False}, format="json")
    assert response.status_code == 400
    assert "unexpected field" in str(response.json())

# ---------------------------------------------------------------- oauth token
def test_token_basic_auth_returns_200_and_bearer_token(api, user, client_app):
    client, secret = client_app
    response = api.post("/api/v1/oauth/token", {"grant_type": "client_credentials", "scope": "read:profile:gaming", "user_id": str(user.id)}, **basic(client, secret))
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer" and body["expires_in"] == 3600 and body["scope"] == "read:profile:gaming"
    assert response["Cache-Control"] == "no-store"

def test_token_accepts_credentials_in_body(api, user, client_app):
    client, secret = client_app
    response = api.post("/api/v1/oauth/token", {"grant_type": "client_credentials", "scope": "read:profile:gaming", "user_id": str(user.id), "client_id": client.client_id,"client_secret": secret})
    assert response.status_code == 200

def test_token_bad_secret_returns_401(api, user, client_app):
    client, _ = client_app
    response = api.post("/api/v1/oauth/token", {"grant_type": "client_credentials", "scope": "read:profile:gaming", "user_id": str(user.id)}, **basic(client, "wrong"))
    assert response.status_code == 401
    assert response.json()["error"] == "invalid_client"

def test_token_wrong_grant_type_returns_400(api, user, client_app):
    response = api.post("/api/v1/oauth/token", {"grant_type": "password", "scope": "read:profile:gaming", "user_id": str(user.id)}, **basic(*client_app))
    assert response.status_code == 400
    assert response.json()["error"] == "unsupported_grant_type"

@pytest.mark.parametrize("scope", ["read:profile:Gaming", "profile:read:gaming", "read:profile", "write:profile:*", "read:profile:gaming read:profile:personal"])

def test_token_invalid_scope_returns_400_with_format_hint(api, user, client_app, scope):
    response = api.post("/api/v1/oauth/token", {"grant_type": "client_credentials", "scope": scope, "user_id": str(user.id)}, **basic(*client_app))
    assert response.status_code == 400
    assert response.json()["error"] == "invalid_scope"
    assert "read:profile:<context>" in response.json()["error_description"]

@pytest.mark.parametrize("user_id", ["", "not-a-uuid", "00000000-0000-00000000-000000000000"])
def test_token_unknown_user_returns_400(api, client_app, user_id):
    response = api.post("/api/v1/oauth/token", {"grant_type": "client_credentials", "scope": "read:profile:gaming", "user_id": user_id}, **basic(*client_app))
    assert response.status_code == 400

# ---------------------------------------------------------------- revoke and jwks
def test_revoke_returns_200(api, user, client_app):
    token = get_token(api, client_app, user, "read:profile:gaming")
    assert api.post("/api/v1/oauth/revoke", {"token": token}, **basic(*client_app)).status_code == 200

def test_revoke_invalid_token_still_returns_200(api, client_app):
    assert api.post("/api/v1/oauth/revoke", {"token": "garbage"}, **basic(*client_app)).status_code == 200

def test_revoke_unknown_client_returns_401(api, client_app):
    client, _ = client_app
    assert api.post("/api/v1/oauth/revoke", {"token": "x"}, **basic(client, "wrong")).status_code == 401

def test_jwks_publishes_key_with_kid(api):
    response = api.get("/api/v1/.well-known/jwks.json")
    assert response.status_code == 200
    key = response.json()["keys"][0]
    assert key["kid"] == "test-key-1" and key["alg"] == "RS256" and key["kty"] == "RSA"
    assert "max-age=600" in response["Cache-Control"]

# ---------------------------------------------------------------- personas and names
def test_persona_read_returns_200_and_shape(api, user, client_app):
    grant(user, client_app[0], "gaming")
    token = get_token(api, client_app, user, "read:profile:gaming")
    response = api.get(f"/api/v1/users/{user.id}/personas/gaming", **bearer(token))
    assert response.status_code == 200
    assert response.json()["context"] == "gaming"
    assert {"attribute_key", "label", "attribute_value", "visibility_level"} <= set(response.json()["attributes"][0])

def test_persona_list_with_wildcard_returns_200(api, user, client_app):
    grant(user, client_app[0], "gaming")
    token = get_token(api, client_app, user, "read:profile:*")
    response = api.get(f"/api/v1/users/{user.id}/personas", **bearer(token))
    assert response.status_code == 200
    assert [p["context"] for p in response.json()["personas"]] == ["gaming"]

def test_persona_patch_by_client_with_write_scope_returns_200(api, user, client_app):
    grant(user, client_app[0], "gaming", "read:profile:gaming write:profile:gaming")
    token = get_token(api, client_app, user, "write:profile:gaming")
    response = api.patch(f"/api/v1/users/{user.id}/personas/gaming", {"attributes": [{"attribute_key": "favourite_game", "attribute_value": "Chess"}]}, format="json", **bearer(token))
    assert response.status_code == 200
    assert any(a["attribute_value"] == "Chess" for a in response.json()["attributes"])

def test_persona_patch_by_owner_sets_visibility_and_deletes(api, user):
    token = login(api, user)
    url = f"/api/v1/users/{user.id}/personas/gaming"
    response = api.patch(url, {"attributes": [{"attribute_key": "avatar_url", "attribute_value": "https://img.example/a.png", "visibility_level": "private"}, {"attribute_key": "gamertag", "attribute_value": None},]}, format="json", **bearer(token, FIRST_PARTY))
    assert response.status_code == 200
    rows = {a["attribute_key"]: a for a in response.json()["attributes"]}
    assert rows["avatar_url"]["visibility_level"] == "private"
    assert "gamertag" not in rows

def test_persona_patch_undefined_key_returns_400(api, user):
    token = login(api, user)
    response = api.patch(f"/api/v1/users/{user.id}/personas/gaming", {"attributes": [{"attribute_key": "shoe_size", "attribute_value": "9"}]}, format="json", **bearer(token, FIRST_PARTY))
    assert response.status_code == 400

@pytest.mark.parametrize("key,value", [("avatar_url", "not a url"), ("gamertag", "")])
def test_persona_patch_invalid_value_returns_400(api, user, key, value):
    token = login(api, user)
    response = api.patch(f"/api/v1/users/{user.id}/personas/gaming", {"attributes": [{"attribute_key": key, "attribute_value": value}]}, format="json", **bearer(token, FIRST_PARTY))
    assert response.status_code == 400
    
def test_persona_unknown_context_returns_404_for_owner(api, user):
    token = login(api, user)
    assert api.get(f"/api/v1/users/{user.id}/personas/dating", **bearer(token, None)).status_code == 404

def test_names_returns_preferred_name_for_context(api, user, client_app):
    grant(user, client_app[0], "personal")
    token = get_token(api, client_app, user, "read:profile:personal")
    response = api.get(f"/api/v1/users/{user.id}/names", **bearer(token))
    assert response.status_code == 200

def test_owner_can_add_and_delete_name(api, user):
    token = login(api, user)
    url = f"/api/v1/users/{user.id}/names"
    created = api.post(url, {"name_value": "Ash", "name_type": "nickname", "context": "gaming", "is_default": True}, format="json", **bearer(token, FIRST_PARTY))
    assert created.status_code == 201
    names = api.get(url, **bearer(token, None)).json()
    assert names["preferred"]["gaming"] == "Ash"
    assert api.delete(f"{url}/{created.json()['id']}", **bearer(token, FIRST_PARTY)).status_code == 204

def test_name_with_end_before_start_returns_400(api, user):
    token = login(api, user)
    response = api.post(f"/api/v1/users/{user.id}/names",
                        {"name_value": "X", "name_type": "legal", "context": "professional","valid_from": "2026-01-01", "valid_to": "2025-01-01"}, format="json",**bearer(token, FIRST_PARTY))
    assert response.status_code == 400

def test_attribute_definitions_list(api, db):
    response = api.get("/api/v1/attribute-definitions?context=gaming")
    assert response.status_code == 200
    assert {d["allowed_context"] for d in response.json()} == {"gaming"}

# ---------------------------------------------------------------- clients
def test_register_client_returns_201_and_secret_once(api, user):
    token = login(api, user)
    response = api.post("/api/v1/clients", {"client_name": "Quiz Night", "registered_domain": "https://Quiz.Example"}, format="json", **bearer(token, FIRST_PARTY))
    assert response.status_code == 201
    body = response.json()
    assert body["client_id"].startswith("cl_") and body["client_secret"]
    assert body["registered_domain"] == "https://quiz.example"
    stored = ApiClient.objects.get(client_id=body["client_id"])
    assert body["client_secret"] not in stored.client_secret_hash
    listed = api.get("/api/v1/clients", **bearer(token, None)).json()
    assert "client_secret" not in listed[0]

@pytest.mark.parametrize("domain", ["ftp://quiz.example", "http://quiz.example", "https://quiz.example/path", "quiz.example", "https://user@quiz.example"])
def test_register_client_bad_domain_returns_400(api, user, domain):
    token = login(api, user)
    response = api.post("/api/v1/clients", {"client_name": "Quiz Night", "registered_domain": domain}, format="json", **bearer(token, FIRST_PARTY))
    assert response.status_code == 400

def test_client_public_info(api, user, client_app):
    token = login(api, user)
    ok = api.get(f"/api/v1/clients/{client_app[0].client_id}", **bearer(token, None))
    assert ok.status_code == 200 and ok.json()["client_name"] == "Arcade Hub"
    assert api.get("/api/v1/clients/cl_missing", **bearer(token, None)).status_code == 404

# ---------------------------------------------------------------- consents
def test_consent_create_list_delete(api, user, client_app):
    token = login(api, user)
    created = api.post("/api/v1/consents", {"client_id": client_app[0].client_id, "persona_context": "gaming"}, format="json", **bearer(token, FIRST_PARTY))
    assert created.status_code == 201
    assert created.json()["scope"] == "read:profile:gaming"
    listed = api.get("/api/v1/consents", **bearer(token, None))
    assert listed.status_code == 200 and len(listed.json()) == 1
    assert api.delete(f"/api/v1/consents/{created.json()['id']}", **bearer(token, FIRST_PARTY)).status_code == 204
    assert api.get("/api/v1/consents", **bearer(token, None)).json() == []

def test_consent_existing_grant_is_updated_with_200(api, user, client_app):
    token = login(api, user)
    payload = {"client_id": client_app[0].client_id, "persona_context": "gaming"}
    api.post("/api/v1/consents", payload, format="json", **bearer(token, FIRST_PARTY))
    payload["scope"] = "read:profile:gaming write:profile:gaming"
    again = api.post("/api/v1/consents", payload, format="json", **bearer(token, FIRST_PARTY))
    assert again.status_code == 200
    assert ConsentGrant.objects.filter(user=user, revoked_at__isnull=True).count() == 1

@pytest.mark.parametrize("payload,message", [
    ({"persona_context": "dating"}, "unknown persona context"),
    ({"client_id": "cl_missing"}, "unknown client"),
    ({"scope": "read:profile:professional"}, "scope must contain"),
    ({"redirect_uri": "https://evil.example/cb"}, "redirect_uri"),
])

def test_consent_invalid_payload_returns_400(api, user, client_app, payload, message):
    token = login(api, user)
    body = {"client_id": client_app[0].client_id, "persona_context": "gaming", **payload}
    response = api.post("/api/v1/consents", body, format="json", **bearer(token, FIRST_PARTY))
    assert response.status_code == 400
    assert message in response.json()["detail"]

def test_consent_redirect_carries_user_id(api, user, client_app):
    token = login(api, user)
    response = api.post("/api/v1/consents", {"client_id": client_app[0].client_id, "persona_context": "gaming", "redirect_uri": f"{CLIENT_ORIGIN}/callback?x=1"},format="json", **bearer(token, FIRST_PARTY))
    assert response.status_code == 201
    assert response.json()["redirect_to"] == f"{CLIENT_ORIGIN}/callback?x=1&user_id={user.id}&persona=gaming"

# ---------------------------------------------------------------- sign-in session
def test_login_sets_httponly_strict_refresh_cookie(api, user):
    response = api.post("/api/v1/auth/login", {"email": user.email, "password": PASSWORD}, format="json", HTTP_ORIGIN=FIRST_PARTY)
    assert response.status_code == 200
    cookie = response.cookies["refresh_token"]
    assert cookie["httponly"] and cookie["samesite"] == "Strict" and cookie["path"] == "/api/v1/auth"
    assert "refresh_token" not in response.json()

def test_login_bad_password_returns_401(api, user):
    response = api.post("/api/v1/auth/login", {"email": user.email, "password": "nope-nope-nope"}, format="json")
    assert response.status_code == 401

def test_refresh_rotates_and_old_cookie_cannot_be_reused(api, user):
    api.post("/api/v1/auth/login", {"email": user.email, "password": PASSWORD}, format="json")
    old = api.cookies["refresh_token"].value
    first = api.post("/api/v1/auth/refresh")
    assert first.status_code == 200 and api.cookies["refresh_token"].value != old
    api.cookies["refresh_token"] = old
    assert api.post("/api/v1/auth/refresh").status_code == 401

def test_logout_revokes_refresh_token(api, user):
    api.post("/api/v1/auth/login", {"email": user.email, "password": PASSWORD}, format="json")
    cookie = api.cookies["refresh_token"].value
    assert api.post("/api/v1/auth/logout").status_code == 204
    api.cookies["refresh_token"] = cookie
    assert api.post("/api/v1/auth/refresh").status_code == 401

# ---------------------------------------------------------------- hardening
def test_payload_over_limit_returns_413(api, db):
    response = api.generic("POST", "/api/v1/users", "x" * (64 * 1024 + 1), content_type="application/json")
    assert response.status_code == 413

def test_security_headers_present(api, db):
    response = api.get("/api/v1/attribute-definitions")
    assert response["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response["Content-Security-Policy"]
    assert response["X-Frame-Options"] == "DENY"

# ---------------------------------------------------------------- CORS
def test_preflight_from_registered_client_origin_is_allowed(api, client_app):
    response = api.options("/api/v1/oauth/token", HTTP_ORIGIN=CLIENT_ORIGIN,HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
    assert response["Access-Control-Allow-Origin"] == CLIENT_ORIGIN

def test_preflight_from_unregistered_origin_gets_no_cors_header(api, client_app):
    response = api.options("/api/v1/oauth/token", HTTP_ORIGIN="https://evil.example",HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST")
    assert "Access-Control-Allow-Origin" not in response