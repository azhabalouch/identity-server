from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from idp.verify import InvalidToken, verify_token

from .decisions import deny

class TokenUser:
    """Minimal user object built from token claims. No database lookup."""

    is_authenticated = True

    def __init__(self, claims):
        self.id = claims["sub"]

class BearerTokenAuthentication(BaseAuthentication):
    """Step 1 of the decision path: RS256 signature, issuer and expiry."""
    def authenticate(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")

        if not header:
            return None
        
        scheme, _, token = header.partition(" ")

        if scheme.lower() != "bearer" or not token:
            deny(request, AuthenticationFailed, "malformed authorization header")
            
        try:
            claims = verify_token(token.strip(), expected_types={"client", "session"})
        except InvalidToken as exc:
            deny(request, AuthenticationFailed, str(exc))

        return TokenUser(claims), claims

    def authenticate_header(self, request):
        return 'Bearer realm="identity-api"'