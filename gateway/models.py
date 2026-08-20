from django.db import models

class AccessLog(models.Model):
    """Audit trail of every access decision."""

    client_id = models.CharField(max_length=40, null=True, blank=True)
    persona_context = models.CharField(max_length=20, null=True, blank=True)
    endpoint = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    decision = models.CharField(max_length=10)  # allow | deny
    reason = models.CharField(max_length=120)
    status_code = models.PositiveSmallIntegerField()
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "access_log"