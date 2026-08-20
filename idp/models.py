from django.db import models

class SigningKey(models.Model):
    """Public half of each RS256 key pair, published through JWKS."""

    kid = models.CharField(max_length=64, primary_key=True)
    public_key = models.TextField()  # PEM
    algorithm = models.CharField(max_length=10, default="RS256")
    created_at = models.DateTimeField(auto_now_add=True)
    rotated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "signing_keys"
    
class RevokedToken(models.Model):
    """Revocation list under RFC 7009. Rows are purged once expires_at 
    passes."""

    jti = models.CharField(max_length=64, primary_key=True)
    client_id = models.CharField(max_length=40, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    revoked_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = "revoked_tokens"