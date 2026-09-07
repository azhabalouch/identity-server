from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from gateway.serializers import StrictSerializer

class RegisterSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, max_length=128)

    def validate_email(self, value):
        return value.lower()
    
    def validate_password(self, value):
        validate_password(value)
        return value

class LoginSerializer(StrictSerializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(max_length=128)