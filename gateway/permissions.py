"""Access decision path (Chapter III, Section E)."""
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated, PermissionDenied
from rest_framework.permissions import BasePermission

from accounts.models import User
from clients.models import ApiClient
from consent.models import ConsentGrant
from idp.verify import is_revoked

from .decisions import deny, record

WILDCARD = "*"

def verify_signature(request):
    """Signature and expiry were checked by BearerTokenAuthentication."""

    if request.auth is None:
        deny(request, NotAuthenticated, "missing token")

    return request.auth

def request_origin(request):
    return request.META.get("HTTP_ORIGIN")

def get_client(client_id):
    return ApiClient.objects.filter(client_id=client_id).first()

def consent_active(user_id, client_pk, persona, scope):
    grants = ConsentGrant.objects.filter(user_id=user_id, client_id=client_pk, revoked_at__isnull=True)

    if persona == WILDCARD:
        return any(s.startswith("read:profile:") for g in grants for s in g.scope.split())
    
    grant = grants.filter(persona_context=persona).first()
    return grant is not None and scope in grant.scope.split()

def account_active(user_id):
    """A session token outlives a deleted account by up to 15 minutes. This check closes that gap."""

    return User.objects.filter(id=user_id, is_active=True).exists()

def first_party_origin_ok(request):
    origin = request_origin(request)
    return origin is None or origin in settings.FIRST_PARTY_ORIGINS

class DenyByDefault(BasePermission):
    """Any view that forgets to choose a permission class is closed."""

    def has_permission(self, request, view):
        record(request, "deny", "no permission class")
        return False
    
class AllowPublic(BasePermission):
    def has_permission(self, request, view):
        record(request, "allow", "public route")
        return True

class SessionPermission(BasePermission):
    """Consumer and corporate tier routes, used by the project's own React client."""

    def has_permission(self, request, view):
        if request.method == "OPTIONS":
            record(request, "allow", "pre-flight")
            return True
        
        claims = verify_signature(request)

        if is_revoked(claims["jti"]):
            deny(request, AuthenticationFailed, "token revoked")

        if claims["typ"] != "session":
            deny(request, PermissionDenied, "session token required")

        if not account_active(claims["sub"]):
            deny(request, AuthenticationFailed, "account deleted")

        if not first_party_origin_ok(request):
            deny(request, PermissionDenied, "origin not registered")

        record(request, "allow", "session")
        return True
    
class PersonaScopePermission(BasePermission):
    """Steps 1 to 5 for every persona and names route."""
    def has_permission(self, request, view):
        if request.method == "OPTIONS":
            record(request, "allow", "pre-flight")
            return True                                        # pre-flight
        
        claims = verify_signature(request)                     # 1. 401 on failure

        if is_revoked(claims["jti"]):                          # 2. revocation list
            deny(request, AuthenticationFailed, "token revoked")

        if str(view.kwargs.get("user_id")) != claims["sub"]:   # object-level check
            deny(request, PermissionDenied, "subject mismatch")

        if claims["typ"] == "session":                         # owner managing own data
            if not account_active(claims["sub"]):
                deny(request, AuthenticationFailed, "account deleted")
            if not first_party_origin_ok(request):
                deny(request, PermissionDenied, "origin not registered")
            record(request, "allow", "owner", persona=view.kwargs.get("context"))
            return True
        client = get_client(claims["client_id"])               # 3. client identity
        extra = {"client_id": claims["client_id"], "persona": claims["persona"]}

        if client is None or request_origin(request) != client.registered_domain:
            deny(request, PermissionDenied, "origin not registered", **extra)

        if not consent_active(claims["sub"], client.pk, claims["persona"], claims["scope"]): # 4. consent record
            deny(request, PermissionDenied, "no active consent", **extra)

        if view.required_scope(request) != claims["scope"]:   # 5. scope
            deny(request, PermissionDenied, "scope mismatch", **extra)

        record(request, "allow", view.required_scope(request), **extra)
        return True