import base64
import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from accounts.models import User
from clients.models import ApiClient
from consent.models import ConsentGrant
from personas.constants import CONTEXTS, PRIVATE, PUBLIC
from personas.models import ContextualName, Persona, PersonaAttribute

TEST_KID = "test-key-1"
CLIENT_ORIGIN = "https://arcade.example"
FIRST_PARTY = "http://localhost:5173"
PASSWORD = "correct-horse-battery-9"

_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_PEM = _private_key.private_bytes(
    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
)
PUBLIC_PEM = _private_key.public_key().public_bytes(
    serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
)

# One clearly private value per persona. Isolation tests assert these never leak.
SECRETS = {"professional": "Northwind-Ltd-SECRET", "personal": "Lahore-SECRET", "gaming": "NightOwl-SECRET"}

@pytest.fixture(autouse=True)
def identity_settings(settings, monkeypatch):
    from idp import signing, verify
    settings.JWT_PRIVATE_KEY_B64 = base64.b64encode(PRIVATE_PEM).decode()
    settings.JWT_KID = TEST_KID
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # speed only
    settings.JWT_ISSUER = "http://testserver/api/v1"
    settings.FIRST_PARTY_ORIGINS = [FIRST_PARTY]
    signing._private_key.cache_clear()
    signing._key_registered = False
    verify._public_keys.clear()
    cache.clear()
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"token": "10000/minute", "login": "10000/minute"})
    yield

@pytest.fixture
def api():
    return APIClient()

def make_user(email):
    user = User.objects.create_user(email, PASSWORD)
    personas = {c: Persona.objects.create(user=user, context=c) for c in CONTEXTS}
    rows = {
        "professional": [("job_title", "Backend Developer", PUBLIC), ("employer", SECRETS["professional"], PRIVATE)],
        "personal": [("pronouns", "she/her", PUBLIC), ("home_city", SECRETS["personal"], PRIVATE)],
        "gaming": [("gamertag", "NightOwl98", PUBLIC), ("discord_handle", SECRETS["gaming"], PRIVATE)],
    }
    for context, items in rows.items():
        for key, value, visibility in items:
            PersonaAttribute.objects.create(persona=personas[context],
                                            attribute_key_id=key,
                                            attribute_value=value, visibility_level=visibility)
            
    ContextualName.objects.create(user=user, name_value="Ayesha Noor Khan", 
                                  name_type="legal",
                                  context="professional", is_default=True)

    ContextualName.objects.create(user=user, name_value="Ayesha",
                                  name_type="preferred",
                                  context="personal", is_default=True)
    ContextualName.objects.create(user=user, name_value="NightOwl98",
                                  name_type="username",
                                  context="gaming", is_default=True)
    return user

@pytest.fixture
def user(db):
    return make_user("ayesha@example.com")

@pytest.fixture
def other_user(db):
    return make_user("bilal@example.com")

@pytest.fixture
def client_app(user):
    """A registered third-party client. Returns (ApiClient, raw secret)."""

    return ApiClient.register(user.id, "Arcade Hub", CLIENT_ORIGIN)

def grant(user, client, context, scope=None):
    return ConsentGrant.objects.create(user=user, client=client,
                                       persona_context=context,
                                       scope=scope or f"read:profile:{context}")

def get_token(api, client_app, user, scope):
    client, secret = client_app
    api.credentials()
    response = api.post("/api/v1/oauth/token",
                        {"grant_type": "client_credentials",
                         "scope": scope, "user_id": str(user.id)},
                         HTTP_AUTHORIZATION="Basic " + base64.b64encode(f"{client.client_id}:{secret}".encode()).decode())
    
    assert response.status_code == 200, response.content
    return response.json()["access_token"]

def login(api, user):
    response = api.post("/api/v1/auth/login",
                        {"email": user.email, "password": PASSWORD},
                        format="json",
                        HTTP_ORIGIN=FIRST_PARTY)
    
    assert response.status_code == 200, response.content
    return response.json()["access_token"]

def bearer(token, origin=CLIENT_ORIGIN):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"}
    if origin:
        headers["HTTP_ORIGIN"] = origin
    return headers

def forge(claims, key=PRIVATE_PEM, kid=TEST_KID, algorithm="RS256", **overrides):
    """Build a token by hand for negative tests (tests may not import idp.signing)."""

    now = int(time.time())
    payload = {"iss": "http://testserver/api/v1", "iat": now, "exp": now + 600, "jti": uuid.uuid4().hex, **claims}
    payload.update(overrides)
    return jwt.encode(payload, key, algorithm=algorithm, headers={"kid": kid})

@pytest.fixture
def ensure_key(db):
    """Store the test public key, as the first real token issue would."""
    from idp.models import SigningKey
    SigningKey.objects.get_or_create(kid=TEST_KID, defaults={"public_key": PUBLIC_PEM.decode()})