"""
Second composite foreign key: the context stored on each attribute row must
match the context of its persona.

Migration 0002 checks (attribute_key, context) against attribute_definitions,
but it does not check that persona_attributes.context equals personas.context.
Without this migration, a raw SQL insert could store a professional key in a
gaming persona by writing context = 'professional' on the row.

The UNIQUE (id, context) constraint on personas is needed because PostgreSQL
only allows a foreign key to reference a unique set of columns. The migration
fails, and changes nothing, if any existing row breaks the new rule.
"""

from django.db import migrations

FORWARD = """
ALTER TABLE personas
    ADD CONSTRAINT personas_id_context_uniq
    UNIQUE (id, context);

ALTER TABLE persona_attributes
    ADD CONSTRAINT persona_attr_persona_context_fk
    FOREIGN KEY (persona_id, context)
    REFERENCES personas (id, context)
    ON DELETE CASCADE;
"""

REVERSE = """
ALTER TABLE persona_attributes DROP CONSTRAINT persona_attr_persona_context_fk;
ALTER TABLE personas DROP CONSTRAINT personas_id_context_uniq;
"""


class Migration(migrations.Migration):
    dependencies = [("personas", "0003_seed_attribute_definitions")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
