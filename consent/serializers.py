from rest_framework import serializers

from gateway.serializers import StrictSerializer

class ConsentCreateSerializer(StrictSerializer):
    client_id = serializers.CharField(max_length=40)
    persona_context = serializers.CharField(max_length=20)
    scope = serializers.CharField(max_length=200, required=False)
    redirect_uri = serializers.CharField(max_length=500, required=False)