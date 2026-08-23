import base64
import secrets

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = "Generate a 2048-bit RSA key pair and print the environment variables to set."

    def handle(self, *args, **options):
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        self.stdout.write(f"JWT_KID=key-{secrets.token_hex(4)}")
        self.stdout.write(f"JWT_PRIVATE_KEY_B64={base64.b64encode(pem).decode()}")
        self.stderr.write("Store these values as secrets. Never commit them to Git.")