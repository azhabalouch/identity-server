from urllib.parse import urlencode, urlsplit, urlunsplit
from django.utils import timezone

from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from clients.models import ApiClient
from clients.serializers import normalise_origin

from gateway.decisions import deny
from gateway.permissions import SessionPermission

from personas.constants import CONTEXTS

from .models import ConsentGrant
from .serializers import ConsentCreateSerializer

def grant_json(grant):
    return {
        "id": str(grant.id),
        "client_id": grant.client.client_id,
        "client_name": grant.client.client_name,
        "registered_domain": grant.client.registered_domain,
        "persona_context": grant.persona_context,
        "scope": grant.scope,
        "granted_at": grant.granted_at,
        "revoked_at": grant.revoked_at,
    }

def bad_request(message):
    return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)

class ConsentListCreateView(APIView):
    """GET and POST /api/v1/consents (consumer tier)."""

    permission_classes = [SessionPermission]

    def get(self, request):
        rows = (ConsentGrant.objects.filter(user_id=request.auth["sub"], revoked_at__isnull=True).select_related("client").order_by("-granted_at"))
        return Response([grant_json(g) for g in rows])
    
    def post(self, request):
        serializer = ConsentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        context = data["persona_context"]

        if context not in CONTEXTS:
            return bad_request("unknown persona context")
        
        client = ApiClient.objects.filter(client_id=data["client_id"]).first()

        if client is None:
            return bad_request("unknown client")
        
        scope = data.get("scope") or f"read:profile:{context}"
        allowed = {f"read:profile:{context}", f"write:profile:{context}"}

        if any(s not in allowed for s in scope.split()):
            return bad_request(f"scope must contain only read:profile:{context} and/or write:profile:{context}")
        
        redirect_to = None

        if data.get("redirect_uri"):
            if normalise_origin(_origin_of(data["redirect_uri"])) != client.registered_domain:
                return bad_request("redirect_uri must be on the client's registered domain")
            
            redirect_to = _add_query(data["redirect_uri"], {"user_id": request.auth["sub"], "persona": context})
            grant = ConsentGrant.objects.filter(
            user_id=request.auth["sub"], client=client, persona_context=context, revoked_at__isnull=True
        ).first()
        created = grant is None

        if created:
            grant = ConsentGrant.objects.create(
                user_id=request.auth["sub"], client=client, persona_context=context, scope=scope
            )

        else:
            grant.scope = scope
            grant.save(update_fields=["scope"])

        body = grant_json(grant)
        body["redirect_to"] = redirect_to
        return Response(body, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    
class ConsentDetailView(APIView):
    """DELETE /api/v1/consents/{id} — withdraw one grant (GDPR Art. 7(3))."""

    permission_classes = [SessionPermission]

    def delete(self, request, grant_id):
        grant = ConsentGrant.objects.filter(id=grant_id).first()

        if grant is None:
            raise NotFound("grant not found")
        
        if str(grant.user_id) != request.auth["sub"]:
            deny(request, PermissionDenied, "grant belongs to another user")

        if grant.revoked_at is None:
            grant.revoked_at = timezone.now()  # keep the row for the audit history
            grant.save(update_fields=["revoked_at"])

        return Response(status=status.HTTP_204_NO_CONTENT)
    
def _origin_of(url):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "", "", ""))

def _add_query(url, params):
    parts = urlsplit(url)
    query = f"{parts.query}&{urlencode(params)}" if parts.query else urlencode(params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, query, parts.fragment))