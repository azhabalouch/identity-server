"""Token signing. Only the idp app may import this module (see 
tests/test_boundaries.py)."""

import base64
import time
import uuid
from functools import lru_cache

import jwt
from cryptography.hazmat.primitives import serialization
from django.conf import settings

from .models import SigningKey

@lru_cache(maxsize=1)
def _private_key():
    # The PEM is held base64-encoded in an environment variable because the
    # Vercel file system is read-only. It is parsed once per warm instance.
    if not settings.JWT_PRIVATE_KEY_B64 or not settings.JWT_KID:
        raise RuntimeError("JWT_PRIVATE_KEY_B64 and JWT_KID must be set")
    pem = base64.b64decode(settings.JWT_PRIVATE_KEY_B64)
    return serialization.load_pem_private_key(pem, password=None)

def public_key_pem():
    return (
        _private_key()
        .public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )

_key_registered = False

def ensure_signing_key_row():
    """Make sure the public half of the current key is in signing_keys."""
    global _key_registered
    if not _key_registered:
        SigningKey.objects.get_or_create(kid=settings.JWT_KID, defaults={"public_key": public_key_pem()})
        _key_registered = True

def _sign(claims, lifetime):
    ensure_signing_key_row()
    now = int(time.time())
    payload = {"iss": settings.JWT_ISSUER, "iat": now, "exp": now + lifetime, "jti": uuid.uuid4().hex, **claims}
    token = jwt.encode(payload, _private_key(), algorithm="RS256", headers={"kid": settings.JWT_KID})
    return token, payload

def issue_client_token(user_id, client_id, scope, persona):
    return _sign(
        {"typ": "client", "sub": str(user_id), "client_id": client_id, "scope": scope, "persona": persona},
        settings.CLIENT_TOKEN_LIFETIME,
    )

def issue_session_token(user_id):
    return _sign({"typ": "session", "sub": str(user_id), "scope": "session"},settings.SESSION_TOKEN_LIFETIME)

def issue_refresh_token(user_id):
    return _sign({"typ": "refresh", "sub": str(user_id), "scope": "refresh"}, settings.REFRESH_TOKEN_LIFETIME)