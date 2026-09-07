from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from gateway.permissions import SessionPermission

from .models import ApiClient
from .serializers import ClientCreateSerializer

def client_json(client):
    return {
        "client_id": client.client_id,
        "client_name": client.client_name,
        "registered_domain": client.registered_domain,
        "created_at": client.created_at,
    }

class ClientListCreateView(APIView):
    """POST /api/v1/clients (corporate tier) and GET for the owner's own clients."""

    permission_classes = [SessionPermission]

    def get(self, request):
        rows = ApiClient.objects.filter(owner_id=request.auth["sub"]).order_by("created_at")
        return Response([client_json(c) for c in rows])
    
    def post(self, request):
        serializer = ClientCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        client, secret = ApiClient.register(request.auth["sub"], **serializer.validated_data)
        data = client_json(client)
        data["client_secret"] = secret
        data["note"] = "Store the client secret now. It is shown once and cannot be recovered."
        return Response(data, status=status.HTTP_201_CREATED)
    
class ClientPublicView(APIView):
    """GET /api/v1/clients/{client_id} — name and domain for the authorisation screen."""

    permission_classes = [SessionPermission]

    def get(self, request, client_id):
        client = ApiClient.objects.filter(client_id=client_id).first()

        if client is None:
            raise NotFound("unknown client")
        
        data = client_json(client)
        data.pop("created_at")
        return Response(data)