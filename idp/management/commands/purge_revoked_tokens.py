from django.core.management.base import BaseCommand
from django.utils import timezone

from idp.models import RevokedToken

class Command(BaseCommand):
    help = "Delete revocation rows whose tokens have already expired."
    
    def handle(self, *args, **options):
        deleted, _ = RevokedToken.objects.filter(expires_at__lt=timezone.now()).delete()
        self.stdout.write(f"Deleted {deleted} expired revocation rows.")