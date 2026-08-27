from django.conf import settings
from django.db import transaction
from django.http import JsonResponse

from .models import AccessLog

class AuditMiddleware:
    """
    Write one access_log row per API request, outside the request transaction.ATOMIC_REQUESTS rolls back the view transaction when access is denied, so a row written inside the view would disappear (Chapter IV, Section G).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith("/api/"):
            return response
        default = ("allow", "pre-flight") if request.method == "OPTIONS" else ("deny", "unhandled")

        decision, reason = getattr(request, "decision", default)

        with transaction.atomic():
            AccessLog.objects.create(
                client_id=getattr(request, "client_id", None),
                persona_context=getattr(request, "persona", None),
                endpoint=request.path[:255],
                method=request.method,
                decision=decision,
                reason=str(reason)[:120],
                status_code=response.status_code,
            )

        return response
    
class MaxBodySizeMiddleware:
    """Reject large payloads before any parser reads them."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            length = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 0

        if length > settings.MAX_REQUEST_BODY_BYTES:
            request.decision = ("deny", "payload too large")
            return JsonResponse({"detail": "payload too large"}, status=413)
        
        return self.get_response(request)
    
class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        response.setdefault("Cache-Control", "no-store")
        response.setdefault("Permissions-Policy", "geolocation=(), camera=(), microphone=()")

        return response