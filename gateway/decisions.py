"""Record access decisions on the Django request so AuditMiddleware can write 
them."""

def record(request, decision, reason, **extra):
    raw = getattr(request, "_request", request)  # DRF Request wraps HttpRequest
    raw.decision = (decision, reason)
    for key, value in extra.items():
        setattr(raw, key, value)

def deny(request, exc_class, reason, **extra):
    record(request, "deny", reason, **extra)
    raise exc_class(reason)