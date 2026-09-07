import base64
import binascii

from .models import ApiClient

def client_credentials(request):
    """Read client_id and client_secret from HTTP Basic auth or the request body."""

    header = request.META.get("HTTP_AUTHORIZATION", "")

    if header.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(header[6:].strip()).decode()
        except (binascii.Error, UnicodeDecodeError):
            return None, None
        
        client_id, _, secret = decoded.partition(":")

        return client_id, secret
    
    return request.data.get("client_id"), request.data.get("client_secret")

def authenticate_client(request):
    client_id, secret = client_credentials(request)

    if not client_id:
        return None
    
    client = ApiClient.objects.filter(client_id=client_id).first()

    if client is None or not client.check_secret(secret):
        return None
    
    return client