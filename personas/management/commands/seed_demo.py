import secrets

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from clients.models import ApiClient, hash_secret
from consent.models import ConsentGrant
from personas.constants import CONTEXTS, PRIVATE, PUBLIC
from personas.models import ContextualName, Persona, PersonaAttribute

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo-password-123"

ATTRIBUTES = {
    "professional": [
        ("job_title", "Backend Developer", PUBLIC),
        ("employer", "Northwind Ltd", PUBLIC),
        ("work_email", "a.khan@northwind.example", PUBLIC)
    ],
    "personal": [
        ("pronouns", "she/her", PUBLIC),
        ("home_city", "Lahore", PRIVATE),
        ("birthday", "1998-04-12", PRIVATE)
    ],
    "gaming": [
        ("gamertag", "NightOwl98", PUBLIC),
        ("favourite_game", "Rocket League", PUBLIC),
        ("discord_handle", "nightowl#2041", PUBLIC)
    ],
}

NAMES = [
    ("Ayesha Noor Khan", "legal", "professional", True),
    ("A. Khan", "professional", "professional", False),
    ("Ayesha", "preferred", "personal", True),
    ("Ashi", "nickname", "personal", False),
    ("NightOwl98", "username", "gaming", True),
]

class Command(BaseCommand):
    help = "Create a demo user with three personas and a demo third-party client."

    def add_arguments(self, parser):
        parser.add_argument("--client-origin", default="http://localhost:5174")

    @transaction.atomic
    def handle(self, *args, **options):
        user = User.objects.filter(email=DEMO_EMAIL).first()

        if user is None:
            user = User.objects.create_user(DEMO_EMAIL, DEMO_PASSWORD)

        personas = {c: Persona.objects.get_or_create(user=user, context=c)[0] for c in CONTEXTS}
        for context, rows in ATTRIBUTES.items():
            for key, value, visibility in rows:
                row = PersonaAttribute.objects.filter(persona=personas[context], attribute_key_id=key).first()
                row = row or PersonaAttribute(persona=personas[context], attribute_key_id=key)
                row.attribute_value, row.visibility_level = value, visibility
                row.save()

        if not user.names.exists():
            for value, name_type, context, default in NAMES:
                ContextualName.objects.create(user=user, name_value=value, name_type=name_type,context=context, is_default=default)

        client = ApiClient.objects.filter(client_name="Arcade Hub (demo)", owner=user).first()

        if client is None:
            client, secret = ApiClient.register(user.id, "Arcade Hub (demo)", options["client_origin"])
        else:  # a secret cannot be read back, so issue a new one
            secret = secrets.token_urlsafe(32)
            client.client_secret_hash = hash_secret(secret)
            client.registered_domain = options["client_origin"]
            client.save()

        ConsentGrant.objects.get_or_create(user=user, client=client, persona_context="gaming",revoked_at__isnull=True, defaults= {"scope": "read:profile:gaming"})

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write(f"  user email      {DEMO_EMAIL}")
        self.stdout.write(f"  user password   {DEMO_PASSWORD}")
        self.stdout.write(f"  user id         {user.id}")
        self.stdout.write(f"  client_id       {client.client_id}")
        self.stdout.write(f"  client_secret   {secret}   (new secret on every run)")
        self.stdout.write(f"  client origin   {client.registered_domain}")