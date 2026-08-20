import uuid

from django.conf import settings
from django.db import models

from .constants import CONTEXT_CHOICES, PUBLIC, VISIBILITY_CHOICES

class Persona(models.Model):
    """One row per context per user. The context never changes after creation."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="personas")
    context = models.CharField(max_length=20, choices=CONTEXT_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "personas"
        constraints = [models.UniqueConstraint(fields=["user", "context"], name="persona_user_context_uniq")]

class AttributeDefinition(models.Model):
    """Controls which attribute keys may exist in which context."""
    DATA_TYPES = [("string", "String"), ("email", "Email"), ("url", "URL"), ("date", "Date")]
    attribute_key = models.CharField(max_length=64, primary_key=True)
    allowed_context = models.CharField(max_length=20, choices=CONTEXT_CHOICES)
    data_type = models.CharField(max_length=10, choices=DATA_TYPES, default="string")
    label = models.CharField(max_length=80)

    class Meta:
        db_table = "attribute_definitions"

class PersonaAttribute(models.Model):
    """Profile data with per-attribute visibility."""
    persona = models.ForeignKey(Persona, on_delete=models.CASCADE, related_name="attributes")
    attribute_key = models.ForeignKey(
        AttributeDefinition, on_delete=models.PROTECT, db_column="attribute_key", related_name="+"
    )
    # Copy of persona.context. It exists only so the composite foreign key in
    # migration 0002 can check (attribute_key, context) at the database layer.
    context = models.CharField(max_length=20, choices=CONTEXT_CHOICES, editable=False)
    attribute_value = models.TextField()
    visibility_level = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default=PUBLIC)

    class Meta:
        db_table = "persona_attributes"
        constraints = [
            models.UniqueConstraint(fields=["persona", "attribute_key"], name="persona_attr_persona_key_uniq")
        ]

    def save(self, *args, **kwargs):
        self.context = self.persona.context  # callers never set this column
        super().save(*args, **kwargs)

class ContextualName(models.Model):
    """Several names per user, each tied to one context."""
    NAME_TYPES = [
        ("legal", "Legal name"),
        ("preferred", "Preferred name"),
        ("professional", "Professional name"),
        ("username", "Username"),
        ("nickname", "Nickname"),
        ("religious", "Religious name"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="names")
    name_value = models.CharField(max_length=150)
    name_type = models.CharField(max_length=20, choices=NAME_TYPES)
    context = models.CharField(max_length=20, choices=CONTEXT_CHOICES)
    visibility_level = models.CharField(max_length=10, choices=VISIBILITY_CHOICES, default=PUBLIC)
    is_default = models.BooleanField(default=False)
    valid_from = models.DateField(null=True, blank=True)
    valid_to = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "contextual_names"
        indexes = [models.Index(fields=["user", "context"], name="names_user_context_idx")]