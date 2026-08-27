from clients.models import ApiClient

def allow_registered_client_origins(sender, request, **kwargs):
    """Allow cross-origin calls only from domains registered in api_clients."""

    origin = request.META.get("HTTP_ORIGIN")
    return bool(origin) and ApiClient.objects.filter(registered_domain=origin).exists()