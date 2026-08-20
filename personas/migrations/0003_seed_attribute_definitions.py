from django.db import migrations

DEFINITIONS = [
    # key, context, data type, label
    ("job_title", "professional", "string", "Job title"),
    ("employer", "professional", "string", "Employer"),
    ("work_email", "professional", "email", "Work email"),
    ("linkedin_url", "professional", "url", "LinkedIn URL"),
    ("office_city", "professional", "string", "Office city"),
    ("pronouns", "personal", "string", "Pronouns"),
    ("personal_email", "personal", "email", "Personal email"),
    ("home_city", "personal", "string", "Home city"),
    ("birthday", "personal", "date", "Birthday"),
    ("gender_identity", "personal", "string", "Gender identity"),
    ("gamertag", "gaming", "string", "Gamertag"),
    ("avatar_url", "gaming", "url", "Avatar URL"),
    ("favourite_game", "gaming", "string", "Favourite game"),
    ("discord_handle", "gaming", "string", "Discord handle"),
]

def seed(apps, schema_editor):
    AttributeDefinition = apps.get_model("personas", "AttributeDefinition")
    for key, context, data_type, label in DEFINITIONS:
        AttributeDefinition.objects.update_or_create(
            attribute_key=key, defaults={"allowed_context": context, "data_type": data_type, "label": label}
        )

def unseed(apps, schema_editor):
    apps.get_model("personas", "AttributeDefinition").objects.filter(
        attribute_key__in=[d[0] for d in DEFINITIONS]
    ).delete()

class Migration(migrations.Migration):
    dependencies = [("personas", "0002_context_fk")]
    operations = [migrations.RunPython(seed, unseed)]