"""Token verification with public keys only. Safe for any app to import."""

from datetime import datetime, timezone

import jwt
from django.conf import settings

from .models import RevokedToken, SigningKey

_public_keys = {}  # kid -> key object, cached for the life of a warm instance

class InvalidToken(Exception):
    pass

def _load_pem(pem):
    return jwt.algorithms.RSAAlgorithm(jwt.algorithms.RSAAlgorithm.SHA256).prepare_key(pem)

def _public_key(kid):
    if kid not in _public_keys:
        row = SigningKey.objects.filter(kid=kid).first()
        if row is None:
            raise InvalidToken("unknown key id")
        _public_keys[kid] = _load_pem(row.public_key)
    return _public_keys[kid]

def verify_token(token, expected_types, verify_exp=True):
    """Check the RS256 signature, issuer and expiry. Return the claims."""
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256":
            raise InvalidToken("algorithm not allowed")
        claims = jwt.decode(
            token,
            _public_key(header.get("kid")),
            algorithms=["RS256"],  # "none" and HS256 are rejected here
            issuer=settings.JWT_ISSUER,
            options={"require": ["exp", "iat", "jti", "sub", "typ"], "verify_exp": verify_exp},
        )
    except jwt.ExpiredSignatureError as exc:
        raise InvalidToken("token expired") from exc
    except jwt.PyJWTError as exc:
        raise InvalidToken("invalid token") from exc
    if claims["typ"] not in expected_types:
        raise InvalidToken("wrong token type")
    return claims

def is_revoked(jti):
    return RevokedToken.objects.filter(jti=jti).exists()

def revoke(claims, client_id=""):
    RevokedToken.objects.get_or_create(
        jti=claims["jti"],
        defaults={
            "client_id": client_id or claims.get("client_id", ""),
            "expires_at": datetime.fromtimestamp(claims["exp"], 
                                                 tz=timezone.utc),
        },
    )

def jwks():
    keys = []
    for row in SigningKey.objects.filter(rotated_at__isnull=True).order_by("created_at"):
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(_load_pem(row.public_key), as_dict=True)
        jwk.update({"kid": row.kid, "alg": "RS256", "use": "sig"})
        keys.append(jwk)
    return {"keys": keys}