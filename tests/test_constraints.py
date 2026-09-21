"""Database constraints hold even when the API is bypassed."""

import pytest
from django.db import IntegrityError, connection, transaction

from consent.models import ConsentGrant
from personas.models import Persona, PersonaAttribute

from .conftest import FIRST_PARTY, bearer, login

pytestmark = pytest.mark.django_db

@pytest.mark.parametrize("context,key", [("gaming", "job_title"), ("gaming", "pronouns"),("professional", "gamertag"), ("personal", "work_email")])
def test_orm_write_of_key_into_wrong_context_fails(user, context, key):
    persona = Persona.objects.get(user=user, context=context)
    with pytest.raises(IntegrityError), transaction.atomic(): PersonaAttribute.objects.create(persona=persona, attribute_key_id=key, attribute_value="x")

def test_orm_write_of_undefined_key_fails(user):
    persona = Persona.objects.get(user=user, context="gaming")
    with pytest.raises(IntegrityError), transaction.atomic(): PersonaAttribute.objects.create(persona=persona, attribute_key_id="shoe_size", attribute_value="9")

def test_raw_sql_bypass_also_fails(user):
    persona = Persona.objects.get(user=user, context="gaming")
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO persona_attributes (persona_id, attribute_key, context, attribute_value, visibility_level)"
            " VALUES (%s, 'job_title', 'gaming', 'x', 'public')", [persona.id])
        
def test_raw_sql_with_mismatched_context_column_fails(user):
    """The row's context must match its persona (migration 0004)."""

    persona = Persona.objects.get(user=user, context="gaming")
    with pytest.raises(IntegrityError), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO persona_attributes (persona_id, attribute_key, context, attribute_value, visibility_level)"
            " VALUES (%s, 'job_title', 'professional', 'x', 'public')", [persona.id])

def test_context_column_is_copied_from_persona(user):
    persona = Persona.objects.get(user=user, context="gaming")
    row = PersonaAttribute(persona=persona, attribute_key_id="avatar_url", attribute_value="https://a.example/x.png")
    row.context = "professional"  # ignored
    row.save()
    assert PersonaAttribute.objects.get(pk=row.pk).context == "gaming"

def test_one_persona_per_context(user):
    with pytest.raises(IntegrityError), transaction.atomic():
        Persona.objects.create(user=user, context="gaming")

def test_one_active_grant_per_client_and_persona(user, client_app):
    ConsentGrant.objects.create(user=user, client=client_app[0], persona_context="gaming", scope="read:profile:gaming")
    with pytest.raises(IntegrityError), transaction.atomic():
        ConsentGrant.objects.create(user=user, client=client_app[0], persona_context="gaming", scope="read:profile:gaming")

def test_composite_foreign_key_exists_in_catalog(db):
    with connection.cursor() as cursor:
        cursor.execute("SELECT conname FROM pg_constraint WHERE conname = 'persona_attr_context_fk'")
        assert cursor.fetchone() is not None

def test_patch_is_all_or_nothing(api, user):
    token = login(api, user)
    response = api.patch(f"/api/v1/users/{user.id}/personas/gaming", {"attributes": [{"attribute_key": "favourite_game", "attribute_value": "Chess"}, {"attribute_key": "job_title", "attribute_value": "Wrong context"}, ]}, format="json", **bearer(token, FIRST_PARTY))
    assert response.status_code == 400
    assert not PersonaAttribute.objects.filter(attribute_value="Chess").exists()

def test_persona_filter_is_part_of_the_sql(user):
    """The persona filter is in the SQL WHERE clause, not applied in 
    Python."""
    
    sql, params = (PersonaAttribute.objects.filter(persona__user_id=user.id, 
    persona__context="gaming")
    .query.sql_with_params())
    assert "personas" in sql and '"context" =' in sql