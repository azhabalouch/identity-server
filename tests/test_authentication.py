"""Authentication failures: every bad token returns 401."""

import base64
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from .conftest import PUBLIC_PEM, bearer, forge, get_token, grant

pytestmark = pytest.mark.django_db

@pytest.fixture
def setup(api, user, client_app, ensure_key):
    grant(user, client_app[0], "gaming")
    base = {"typ": "client", "sub": str(user.id), "client_id": client_app[0].client_id, "scope": "read:profile:gaming", "persona": "gaming"}
    return user, base

def read(api, user, token):
    return api.get(f"/api/v1/users/{user.id}/personas/gaming", **bearer(token))

def test_valid_forged_token_is_accepted_as_control(api, setup):
    user, base = setup
    assert read(api, user, forge(base)).status_code == 200

def test_missing_token_returns_401_with_challenge(api, setup):
    user, _ = setup
    response = api.get(f"/api/v1/users/{user.id}/personas/gaming", HTTP_ORIGIN="https://arcade.example")
    assert response.status_code == 401
    assert response["WWW-Authenticate"].startswith("Bearer")

def test_wrong_scheme_returns_401(api, setup):
    user, base = setup
    response = api.get(f"/api/v1/users/{user.id}/personas/gaming", HTTP_AUTHORIZATION="Basic abc")
    assert response.status_code == 401

def test_garbage_token_returns_401(api, setup):
    user, _ = setup
    assert read(api, user, "not.a.jwt").status_code == 401

def test_expired_token_returns_401(api, setup):
    user, base = setup
    response = read(api, user, forge(base, exp=int(time.time()) - 10))
    assert response.status_code == 401
    assert response.json()["detail"] == "token expired"

def test_token_signed_with_wrong_key_returns_401(api, setup):
    user, base = setup
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes( serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    assert read(api, user, forge(base, key=other)).status_code == 401

def test_unsigned_none_algorithm_returns_401(api, setup):
    user, base = setup
    header = base64.urlsafe_b64encode(b'{"alg":"none","kid":"test-key1"}').rstrip(b"=").decode()
    payload = jwt.utils.base64url_encode(jwt.api_jws.json.dumps({**base, "iss": "http://testserver/api/v1", "iat": int(time.time()), "exp": int(time.time()) + 600, "jti": "x"}).encode()).decode()
    assert read(api, user, f"{header}.{payload}.").status_code == 401

def test_hs256_algorithm_confusion_returns_401(api, setup):
    user, base = setup
    header = jwt.utils.base64url_encode(b'{"alg":"HS256","typ":"JWT","kid":"test-key-1"}')
    body = jwt.utils.base64url_encode(jwt.api_jws.json.dumps({**base, "iss": "http://testserver/api/v1", "iat": int(time.time()), "exp": int(time.time()) + 600, "jti": "y"}).encode())
    import hashlib
    import hmac
    signature = jwt.utils.base64url_encode(hmac.new(PUBLIC_PEM, header + b"." + body, hashlib.sha256).digest())
    assert read(api, user, (header + b"." + body + b"." + signature).decode()).status_code == 401

def test_wrong_issuer_returns_401(api, setup):
    user, base = setup
    assert read(api, user, forge(base, iss="https://evil.example")).status_code == 401

def test_unknown_kid_returns_401(api, setup):
    user, base = setup
    assert read(api, user, forge(base, kid="no-such-key")).status_code == 401

def test_tampered_payload_returns_401(api, setup):
    user, base = setup
    header, payload, signature = forge(base).split(".")
    changed = jwt.utils.base64url_encode(jwt.utils.base64url_decode(payload).replace(b'"gaming"', b'"professional"')).decode()
    assert read(api, user, f"{header}.{changed}.{signature}").status_code == 401

def test_refresh_token_cannot_be_used_as_bearer(api, setup):
    user, base = setup
    assert read(api, user, forge({**base, "typ": "refresh"})).status_code == 401

def test_token_missing_required_claim_returns_401(api, setup):
    user, base = setup
    claims = dict(base)
    claims.pop("typ")
    assert read(api, user, forge(claims)).status_code == 401

def test_revoked_token_returns_401(api, user, client_app):
    grant(user, client_app[0], "gaming")
    token = get_token(api, client_app, user, "read:profile:gaming")
    client, secret = client_app
    api.post("/api/v1/oauth/revoke", {"token": token}, HTTP_AUTHORIZATION="Basic " + base64.b64encode(f"{client.client_id}:{secret}".encode()).decode())
    response = read(api, user, token)
    assert response.status_code == 401
    assert response.json()["detail"] == "token revoked"

def test_client_cannot_revoke_another_clients_token(api, user, client_app):
    from clients.models import ApiClient
    grant(user, client_app[0], "gaming")
    token = get_token(api, client_app, user, "read:profile:gaming")
    rival, rival_secret = ApiClient.register(user.id, "Rival", "https://rival.example")
    api.post("/api/v1/oauth/revoke", {"token": token}, HTTP_AUTHORIZATION="Basic " + base64.b64encode(f"{rival.client_id}:{rival_secret}".encode()).decode())
    assert read(api, user, token).status_code == 200

def test_session_route_without_token_returns_401(api, db):
    assert api.get("/api/v1/consents").status_code == 401