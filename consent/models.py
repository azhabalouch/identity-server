import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from personas.constants import CONTEXT_CHOICES
class ConsentGrant(models.Model):
    """Grant and revocation record, per user, per client, per persona context."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="consents")
    client = models.ForeignKey("clients.ApiClient", on_delete=models.CASCADE, related_name="consents")
    persona_context = models.CharField(max_length=20, choices=CONTEXT_CHOICES)
    scope = models.CharField(max_length=200)  # space-delimited, e.g. "read:profile:gaming"
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "consent_grants"
        indexes = [
            models.Index(fields=["user", "client", "persona_context", "revoked_at"], name="consent_lookup_idx")
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "client", "persona_context"],
                condition=Q(revoked_at__isnull=True),
                name="consent_one_active_grant",
            )
        ]