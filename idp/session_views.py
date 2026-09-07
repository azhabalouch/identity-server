"""Sign-in for the consumer tier. Session tokens are signed here, inside idp."""

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password

from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.models import User
from accounts.serializers import LoginSerializer

from gateway.decisions import record
from gateway.permissions import AllowPublic, first_party_origin_ok

from . import signing, verify

DUMMY_HASH = make_password("timing-equaliser")  # keeps unknown-email logins as slow as real ones

def session_response(user):
    access, access_claims = signing.issue_session_token(user.id)
    refresh, _ = signing.issue_refresh_token(user.id)
    response = Response(
        {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": access_claims["exp"] - access_claims["iat"],
            "user": {"id": str(user.id), "email": user.email},
        },
        headers={"Cache-Control": "no-store"},
    )
    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh,
        max_age=settings.REFRESH_TOKEN_LIFETIME,
        path=settings.REFRESH_COOKIE_PATH,
        secure=settings.REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite="Strict",
    )
    return response

def signed_out(request, reason):
    record(request, "deny", reason)
    response = Response({"detail": "not signed in"}, status=status.HTTP_401_UNAUTHORIZED)
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH, samesite="Strict")
    return response

class FirstPartyView(APIView):
    """Cookie routes: only the project's own client origin may call them."""

    authentication_classes = []
    permission_classes = [AllowPublic]
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)

        if not first_party_origin_ok(request):
            record(request, "deny", "origin not registered")
            raise PermissionDenied("origin not registered")
        
class LoginView(FirstPartyView):
    """POST /api/v1/auth/login"""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        user = User.objects.filter(email=email, is_active=True).first()
        valid = check_password(serializer.validated_data["password"], user.password if user else DUMMY_HASH)

        if user is None or not valid:
            record(request, "deny", "bad credentials")
            return Response({"detail": "invalid email or password"}, status=status.HTTP_401_UNAUTHORIZED)
        
        record(request, "allow", "login")
        return session_response(user)
    
class RefreshView(FirstPartyView):
    """POST /api/v1/auth/refresh — one-time refresh tokens (rotation)."""

    def post(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME, "")

        try:
            claims = verify.verify_token(raw, {"refresh"})
        except verify.InvalidToken as exc:
            return signed_out(request, str(exc))
        
        user = User.objects.filter(id=claims["sub"], is_active=True).first()

        if user is None or verify.is_revoked(claims["jti"]):
            return signed_out(request, "refresh token revoked")
        
        verify.revoke(claims)
        record(request, "allow", "refresh")
        return session_response(user)
    
class LogoutView(FirstPartyView):
    """POST /api/v1/auth/logout"""

    def post(self, request):
        raw = request.COOKIES.get(settings.REFRESH_COOKIE_NAME, "")

        try:
            verify.revoke(verify.verify_token(raw, {"refresh"}, verify_exp=False))
        except verify.InvalidToken:
            pass

        record(request, "allow", "logout")
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=settings.REFRESH_COOKIE_PATH, samesite="Strict")
        return response