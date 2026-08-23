from django.core.management.base import BaseCommand

from idp.signing import ensure_signing_key_row

class Command(BaseCommand):
    help = "Write the public half of the current signing key (JWT_KID) to signing_keys."
    
    def handle(self, *args, **options):
        ensure_signing_key_row()
        self.stdout.write(self.style.SUCCESS("Signing key registered."))