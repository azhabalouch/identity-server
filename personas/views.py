from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator, URLValidator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.views import APIView

from consent.models import ConsentGrant
from gateway.permissions import WILDCARD, AllowPublic, PersonaScopePermission

from .constants import ALL_LEVELS, CLIENT_VISIBLE_LEVELS, CONTEXTS, PRIVATE
from .models import AttributeDefinition, ContextualName, Persona, PersonaAttribute
from .serializers import NameWriteSerializer, PersonaPatchSerializer, attribute_json, name_json

OWNER_ONLY = "owner-only"  # never equal to a client scope, so clients get 403 scope mismatch

def is_owner(claims):
    return claims["typ"] == "session"

def allowed_levels(claims):
    return ALL_LEVELS if is_owner(claims) else CLIENT_VISIBLE_LEVELS

def consented_contexts(claims, action="read"):
    """Persona contexts this client may see for this user, from active grants."""

    if is_owner(claims):
        return list(CONTEXTS)
    grants = ConsentGrant.objects.filter(
        user_id=claims["sub"], client__client_id=claims["client_id"], revoked_at__isnull=True
    )

    return [g.persona_context for g in grants if f"{action}:profile:{g.persona_context}" in g.scope.split()]

class PersonaListView(APIView):
    """GET /api/v1/users/{id}/personas"""

    permission_classes = [PersonaScopePermission]

    def required_scope(self, request):
        return "read:profile:*"
    
    def get(self, request, user_id):
        claims = request.auth
        contexts = consented_contexts(claims)
        rows = (PersonaAttribute.objects
                .filter(persona__user_id=claims["sub"],
                        persona__context__in=contexts,
                        visibility_level__in=allowed_levels(claims))
                .select_related("persona", "attribute_key")
                .order_by("attribute_key_id"))
        grouped = {c: [] for c in contexts}

        for row in rows:
            grouped[row.persona.context].append(attribute_json(row))

        return Response({"personas": [{"context": c, "attributes": a} for c, 
                                      a in grouped.items()]})
    
class PersonaDetailView(APIView):
    """GET and PATCH /api/v1/users/{id}/personas/{context}"""

    permission_classes = [PersonaScopePermission]

    def required_scope(self, request):
        action = "read" if request.method == "GET" else "write"
        return f"{action}:profile:{self.kwargs['context']}"
    
    def context(self):
        claims = self.request.auth
        context = self.kwargs["context"] if is_owner(claims) else claims["persona"]

        if context not in CONTEXTS:
            raise NotFound("unknown persona context")
        
        return context
    
    def get_queryset(self):
        claims = self.request.auth
        return (PersonaAttribute.objects
                .filter(persona__user_id=claims["sub"],
                        persona__context=self.context(),
                        visibility_level__in=allowed_levels(claims))
                .select_related("persona", "attribute_key")
                .order_by("attribute_key_id"))
    
    def get(self, request, user_id, context):
        return Response({"context": self.context(), "attributes": [attribute_json(r) for r in self.get_queryset()]})
    
    def patch(self, request, user_id, context):
        claims = request.auth
        context = self.context()
        serializer = PersonaPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        items = serializer.validated_data["attributes"]
        persona = Persona.objects.get(user_id=claims["sub"], context=context)
        definitions = AttributeDefinition.objects.in_bulk([i["attribute_key"] for i in items])
        errors = {}
        
        for item in items:
            if not is_owner(claims) and "visibility_level" in item:
                errors[item["attribute_key"]] = "clients cannot change visibility"

            elif item["attribute_value"] is not None and item["attribute_key"] in definitions:
                problem = type_problem(definitions[item["attribute_key"]].data_type, item["attribute_value"])
                
                if problem:
                    errors[item["attribute_key"]] = problem
        if errors:
            return Response({"detail": "invalid attributes", "errors": errors}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            with transaction.atomic():  # savepoint: all attributes are saved, or none
                for item in items:
                    self.apply(persona, item, claims)

        except IntegrityError:
            # The composite foreign key rejects keys that are undefined or belong to
            # another context. The database decides, not this view.
            keys = ", ".join(i["attribute_key"] for i in items)
            return Response({"detail": f"undefined attribute key for the {context} context (sent: {keys})"}, status=status.HTTP_400_BAD_REQUEST)
        
        except PermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        
        return self.get(request, user_id, context)
    
    @staticmethod
    def apply(persona, item, claims):
        existing = PersonaAttribute.objects.filter(persona=persona, attribute_key_id=item["attribute_key"]).first()

        if existing and existing.visibility_level == PRIVATE and not is_owner(claims):
            raise PermissionError("clients cannot write private attributes")
        
        if item["attribute_value"] is None:
            if existing:
                existing.delete()
            return
        
        row = existing or PersonaAttribute(persona=persona, attribute_key_id=item["attribute_key"])
        row.attribute_value = item["attribute_value"]

        if "visibility_level" in item:
            row.visibility_level = item["visibility_level"]

        row.save()

def type_problem(data_type, value):
    try:
        if data_type == "email":
            EmailValidator()(value)
        elif data_type == "url":
            URLValidator(schemes=["https", "http"])(value)
        elif data_type == "date" and parse_date(value) is None:
            return "expected a date in YYYY-MM-DD format"
    except (DjangoValidationError, ValueError):
        return f"expected a valid {data_type}"
    return None

class NamesView(APIView):
    """GET /api/v1/users/{id}/names (clients and owner), POST (owner only)."""

    permission_classes = [PersonaScopePermission]

    def required_scope(self, request):
        if request.method != "GET":
            return OWNER_ONLY
        
        persona = request.auth.get("persona")
        return "read:profile:*" if persona == WILDCARD else f"read:profile:{persona}"
    
    def get(self, request, user_id):
        claims = request.auth
        contexts = consented_contexts(claims)

        if not is_owner(claims) and claims["persona"] != WILDCARD:
            contexts = [c for c in contexts if c == claims["persona"]]

        requested = request.query_params.get("context")

        if requested:
            contexts = [c for c in contexts if c == requested]

        today = timezone.now().date()
        rows = ContextualName.objects.filter(
            user_id=claims["sub"], context__in=contexts, visibility_level__in=allowed_levels(claims)
        )
        if not is_owner(claims):
            rows = rows.filter(Q(valid_from__isnull=True) | Q(valid_from__lte=today),
                               Q(valid_to__isnull=True) | Q(valid_to__gte=today))
            
        rows = list(rows.order_by("context", "-is_default", "id"))
        preferred = {}

        for row in rows:
            preferred.setdefault(row.context, row.name_value)  # default name first, else oldest
        return Response({"preferred": preferred, "names": [name_json(r) for r in rows]})
    
    def post(self, request, user_id):
        serializer = NameWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            if data.get("is_default"):
                ContextualName.objects.filter(user_id=user_id, context=data["context"]).update(is_default=False)

            row = ContextualName.objects.create(user_id=user_id, **data)
        return Response(name_json(row), status=status.HTTP_201_CREATED)
    
class NameDetailView(APIView):
    """DELETE /api/v1/users/{id}/names/{name_id} (owner only)."""

    permission_classes = [PersonaScopePermission]

    def required_scope(self, request):
        return OWNER_ONLY
    
    def delete(self, request, user_id, name_id):
        deleted, _ = ContextualName.objects.filter(user_id=user_id, id=name_id).delete()

        if not deleted:
            raise NotFound("name not found")
        return Response(status=status.HTTP_204_NO_CONTENT)
    
class AttributeDefinitionListView(APIView):
    """GET /api/v1/attribute-definitions"""

    authentication_classes = []
    permission_classes = [AllowPublic]
    def get(self, request):
        rows = AttributeDefinition.objects.order_by("allowed_context", "attribute_key")
        context = request.query_params.get("context")

        if context:
            rows = rows.filter(allowed_context=context)

        return Response([{
                "attribute_key": r.attribute_key,
                "allowed_context": r.allowed_context,
                "data_type": r.data_type,
                "label": r.label
            }
            for r in rows
        ])