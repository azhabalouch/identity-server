from urllib.parse import urlsplit

from rest_framework import serializers

from gateway.serializers import StrictSerializer

LOCAL_HOSTS = {"localhost", "127.0.0.1"}

def normalise_origin(value):
    """Return scheme://host[:port], or None if the value is not a plain origin."""

    try:
        parts = urlsplit(value.strip())
    except ValueError:
        return None
    
    if not parts.hostname or parts.path not in ("", "/") or parts.query or parts.fragment or parts.username:
        return None
    
    if parts.scheme == "https" or (parts.scheme == "http" and parts.hostname in LOCAL_HOSTS):
        return f"{parts.scheme}://{parts.netloc.lower()}"
    
    return None

class ClientCreateSerializer(StrictSerializer):
    client_name = serializers.CharField(min_length=3, max_length=100)
    registered_domain = serializers.CharField(max_length=255)

    def validate_registered_domain(self, value):
        origin = normalise_origin(value)

        if origin is None:
            raise serializers.ValidationError( "unregistered domain: send an origin such as https://app.example.com" "(http is allowed only for localhost)")
        
        return origin