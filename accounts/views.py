from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from gateway.decisions import deny, record
from gateway.permissions import AllowPublic, SessionPermission

from idp import verify

from personas.constants import CONTEXTS
from personas.models import Persona

from .models import User
from .serializers import RegisterSerializer

class RegisterView(APIView):
    """POST /api/v1/users — creates the account and its three personas."""

    authentication_classes = []
    permission_classes = [AllowPublic]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if User.objects.filter(email=data["email"]).exists():
            record(request, "deny", "email in use")
            return Response({"detail": "email already in use"}, status=status.HTTP_409_CONFLICT)
        
        try:
            with transaction.atomic():
                user = User.objects.create_user(data["email"], data["password"])
                Persona.objects.bulk_create([Persona(user=user, context=c) for c in CONTEXTS])
        except IntegrityError:  # two requests raced for the same email
            record(request, "deny", "email in use")
            return Response({"detail": "email already in use"}, status=status.HTTP_409_CONFLICT)
        
        return Response({"id": str(user.id), "email": user.email}, status=status.HTTP_201_CREATED)

class UserDetailView(APIView):
    """DELETE /api/v1/users/{id} — the account owner erases the whole identity (GDPR Art. 17)."""

    permission_classes = [SessionPermission]  # client tokens get 403 "session token required"

    def delete(self, request, user_id):
        claims = request.auth

        if str(user_id) != claims["sub"]:
            deny(request, PermissionDenied, "not the account owner")

        # The foreign keys cascade: personas, persona attributes, contextual names,
        # consent grants and the API clients this user registered are all removed.
        User.objects.filter(id=user_id).delete()

        # Revoke the token used for this request. Other session and refresh tokens
        # fail the account check, and client tokens fail the consent check.
        verify.revoke(claims)

        record(request, "allow", "account deleted")
        return Response(status=status.HTTP_204_NO_CONTENT)
