from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from gateway.decisions import record
from gateway.permissions import AllowPublic

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