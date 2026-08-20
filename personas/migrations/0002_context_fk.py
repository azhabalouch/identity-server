"""
- Composite foreign key: an attribute key can only be stored in its allowed 
context.
- The Django ORM cannot express composite foreign keys, so the rule is written 
in SQL.
- The constraint is NOT DEFERRABLE, so an invalid row fails at INSERT time.
"""

from django.db import migrations

FORWARD = """
ALTER TABLE attribute_definitions
    ADD CONSTRAINT attr_def_key_context_uniq
    UNIQUE (attribute_key, allowed_context);

ALTER TABLE persona_attributes
    ADD CONSTRAINT persona_attr_context_fk
    FOREIGN KEY (attribute_key, context)
    REFERENCES attribute_definitions (attribute_key, allowed_context);
"""

REVERSE = """
ALTER TABLE persona_attributes DROP CONSTRAINT persona_attr_context_fk;
ALTER TABLE attribute_definitions DROP CONSTRAINT attr_def_key_context_uniq;
"""

class Migration(migrations.Migration):
    dependencies = [("personas", "0001_initial")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]