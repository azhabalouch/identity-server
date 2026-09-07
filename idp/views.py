import uuid

from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import User
from clients.auth import authenticate_client
from gateway.decisions import record
from gateway.permissions import AllowPublic

from . import signing, verify
from .scopes import SCOPE_FORMAT_HINT, parse_scope

NO_STORE = {"Cache-Control": "no-store"}

class RecordInView(BasePermission):
    """The view itself records the decision, because it depends on client credentials."""

    def has_permission(self, request, view):
        return True
    
def oauth_error(request, code, description, http_status, client_id=None):
    record(request, "deny", code, client_id=client_id)
    headers = dict(NO_STORE)

    if http_status == 401:
        headers["WWW-Authenticate"] = 'Basic realm="identity-api"'

    body = {"error": code, "error_description": description}
    return Response(body, status=http_status, headers=headers)

class TokenView(APIView):
    """POST /api/v1/oauth/token — Client Credentials grant with a user subject."""

    authentication_classes = []
    permission_classes = [RecordInView]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "token"

    def post(self, request):
        client = authenticate_client(request)

        if client is None:
            return oauth_error(request, "invalid_client", "unknown client or wrong secret", 401)
        
        if request.data.get("grant_type") != "client_credentials":
            return oauth_error(request, "unsupported_grant_type", "use grant_type=client_credentials", 400, client.client_id)
        
        scope = request.data.get("scope", "")
        parsed = parse_scope(scope)

        if parsed is None:
            return oauth_error(request, "invalid_scope", f"'{scope}' is not valid. {SCOPE_FORMAT_HINT}", 400, client.client_id)
        
        try:
            user = User.objects.filter(id=uuid.UUID(str(request.data.get("user_id"))), is_active=True).first()
        except ValueError:
            user = None

        if user is None:
            return oauth_error(request, "invalid_request", "user_id is missing or unknown", 400, client.client_id)
        
        token, claims = signing.issue_client_token(user.id, client.client_id, scope, parsed[1])
        record(request, "allow", "token issued", client_id=client.client_id, persona=parsed[1])

        return Response(
            {"access_token": token, "token_type": "Bearer", "expires_in": claims["exp"] - claims["iat"],
             "scope": scope},
            headers=NO_STORE,
        )
class RevokeView(APIView):
    """POST /api/v1/oauth/revoke — RFC 7009. Returns 200 even for invalid tokens."""

    authentication_classes = []
    permission_classes = [RecordInView]

    def post(self, request):
        client = authenticate_client(request)

        if client is None:
            return oauth_error(request, "invalid_client", "unknown client or wrong secret", 401)
        
        try:
            claims = verify.verify_token(request.data.get("token", ""), {"client"}, verify_exp=False)

            if claims["client_id"] == client.client_id:
                verify.revoke(claims, client.client_id)

        except verify.InvalidToken:
            pass  # the endpoint must not reveal token state

        record(request, "allow", "revocation processed", client_id=client.client_id)
        return Response(status=status.HTTP_200_OK, headers=NO_STORE)
    
class JwksView(APIView):
    """GET /api/v1/.well-known/jwks.json"""
    authentication_classes = []
    permission_classes = [AllowPublic]
    
    def get(self, request):
        signing.ensure_signing_key_row()
        return Response(verify.jwks(), headers={"Cache-Control": "public, max-age=600"})