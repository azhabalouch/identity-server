import hashlib
import hmac
import secrets

from django.conf import settings
from django.db import models

def hash_secret(raw):
    # Client secrets are 256-bit random values, so a fast hash is enough;
    # slow password hashers only help against low-entropy human passwords.
    return hashlib.sha256(raw.encode()).hexdigest()

class ApiClient(models.Model):
    """Corporate tier registration."""

    THIRD_PARTY = "third_party"
    FIRST_PARTY = "first_party"
    ROLE_CHOICES = [(THIRD_PARTY, "Third party"), (FIRST_PARTY, "First party")]

    client_id = models.CharField(max_length=40, unique=True)
    client_secret_hash = models.CharField(max_length=64)
    client_name = models.CharField(max_length=100)
    registered_domain = models.CharField(max_length=255)  # an origin, e.g. https://app.example.com
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=THIRD_PARTY)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="api_clients")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "api_clients"

    @classmethod
    def register(cls, owner_id, client_name, registered_domain):
        raw_secret = secrets.token_urlsafe(32)
        client = cls.objects.create(
            client_id=f"cl_{secrets.token_hex(12)}",
            client_secret_hash=hash_secret(raw_secret),
            client_name=client_name,
            registered_domain=registered_domain,
            owner_id=owner_id,
        )
        return client, raw_secret  # the raw secret is shown once and never stored
    
    def check_secret(self, raw):
        return hmac.compare_digest(self.client_secret_hash, hash_secret(raw or ""))