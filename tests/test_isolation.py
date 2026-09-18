"""Cross-persona isolation (requirement R5). A pass needs the right status AND no leaked value."""

import itertools

import pytest

from personas.constants import CONTEXTS

from .conftest import FIRST_PARTY, SECRETS, bearer, get_token, grant, login

pytestmark = pytest.mark.django_db

PAIRS = [(a, b) for a, b in itertools.permutations(CONTEXTS, 2)]
VISIBLE = {"professional": "Backend Developer", "personal": "she/her", "gaming": "NightOwl98"}

def no_leak(response, *contexts):
    body = response.content.decode()
    for context in contexts:
        assert SECRETS[context] not in body
        assert VISIBLE[context] not in body

@pytest.mark.parametrize("token_context,target", PAIRS)
def test_read_token_cannot_read_other_persona(api, user, client_app, token_context, target):
    grant(user, client_app[0], token_context)
    token = get_token(api, client_app, user, f"read:profile:{token_context}")
    response = api.get(f"/api/v1/users/{user.id}/personas/{target}", **bearer(token))
    assert response.status_code == 403
    no_leak(response, target)

@pytest.mark.parametrize("token_context,target", PAIRS)
def test_write_token_cannot_write_other_persona(api, user, client_app, 
token_context, target):
    grant(user, client_app[0], token_context, f"read:profile:{token_context} write:profile:{token_context}")
    token = get_token(api, client_app, user, f"write:profile:{token_context}")
    key = {"professional": "job_title", "personal": "pronouns", "gaming": "gamertag"}[target]
    response = api.patch(f"/api/v1/users/{user.id}/personas/{target}",
                         {"attributes": [{"attribute_key": key, "attribute_value": "HACKED"}]}, format="json", **bearer(token))
    assert response.status_code == 403
    from personas.models import PersonaAttribute
    assert not PersonaAttribute.objects.filter(attribute_value="HACKED").exists()

@pytest.mark.parametrize("context", CONTEXTS)
def test_client_never_receives_private_attributes(api, user, client_app, context):
    grant(user, client_app[0], context)
    token = get_token(api, client_app, user, f"read:profile:{context}")
    response = api.get(f"/api/v1/users/{user.id}/personas/{context}", **bearer(token))
    assert response.status_code == 200
    assert VISIBLE[context] in response.content.decode()
    assert SECRETS[context] not in response.content.decode()

@pytest.mark.parametrize("context", CONTEXTS)
def test_own_persona_read_contains_no_other_persona_values(api, user, client_app, context):
    grant(user, client_app[0], context)
    token = get_token(api, client_app, user, f"read:profile:{context}")
    response = api.get(f"/api/v1/users/{user.id}/personas/{context}", **bearer(token))
    assert response.status_code == 200
    no_leak(response, *[c for c in CONTEXTS if c != context])

@pytest.mark.parametrize("context", CONTEXTS)
def test_names_route_returns_only_token_persona(api, user, client_app, context):
    for c in CONTEXTS:
        grant(user, client_app[0], c)
    token = get_token(api, client_app, user, f"read:profile:{context}")
    response = api.get(f"/api/v1/users/{user.id}/names", **bearer(token))
    assert response.status_code == 200
    assert {n["context"] for n in response.json()["names"]} == {context}

def test_wildcard_names_only_returns_consented_personas(api, user, client_app):
    """Regression test for the names-route defect (Chapter V, Section C)."""

    grant(user, client_app[0], "gaming")
    token = get_token(api, client_app, user, "read:profile:*")
    response = api.get(f"/api/v1/users/{user.id}/names", **bearer(token))
    assert response.status_code == 200
    assert "Ayesha Noor Khan" not in response.content.decode()
    assert {n["context"] for n in response.json()["names"]} == {"gaming"}

def test_wildcard_names_hide_private_names(api, user, client_app):
    from personas.models import ContextualName
    ContextualName.objects.create(user=user, name_value="Hidden Name",
                                  name_type="religious",
                                  context="gaming", 
                                  visibility_level="private")
    grant(user, client_app[0], "gaming")
    token = get_token(api, client_app, user, "read:profile:*")
    assert "Hidden Name" not in api.get(f"/api/v1/users/{user.id}/names", **bearer(token)).content.decode()

def test_wildcard_names_hide_names_outside_validity_window(api, user, client_app):
    from personas.models import ContextualName
    ContextualName.objects.create(user=user, name_value="Old Name", name_type="legal", context="gaming",
                                  valid_from="2000-01-01", valid_to="2001-01-01")
    grant(user, client_app[0], "gaming")
    token = get_token(api, client_app, user, "read:profile:gaming")
    assert "Old Name" not in api.get(f"/api/v1/users/{user.id}/names", **bearer(token)).content.decode()

def test_wildcard_persona_list_only_returns_consented_personas(api, user, client_app):
    grant(user, client_app[0], "personal")
    token = get_token(api, client_app, user, "read:profile:*")
    response = api.get(f"/api/v1/users/{user.id}/personas", **bearer(token))
    assert [p["context"] for p in response.json()["personas"]] == ["personal"]
    no_leak(response, "professional", "gaming")

@pytest.mark.parametrize("path", ["personas/gaming", "names"])
def test_token_for_one_user_cannot_read_another_user(api, user, other_user, client_app, path):
    grant(user, client_app[0], "gaming")
    token = get_token(api, client_app, user, "read:profile:gaming")
    response = api.get(f"/api/v1/users/{other_user.id}/{path}", **bearer(token))
    assert response.status_code == 403
    assert response.json()["detail"] == "subject mismatch"

def test_owner_session_cannot_read_another_user(api, user, other_user):
    token = login(api, user)
    response = api.get(f"/api/v1/users/{other_user.id}/personas/professional", **bearer(token, FIRST_PARTY))
    assert response.status_code == 403

def test_client_cannot_change_visibility(api, user, client_app):
    grant(user, client_app[0], "gaming", "read:profile:gaming write:profile:gaming")
    token = get_token(api, client_app, user, "write:profile:gaming")
    response = api.patch(f"/api/v1/users/{user.id}/personas/gaming",
                         {
                            "attributes": [{
                                "attribute_key": "gamertag",
                                "attribute_value": "X",
                                "visibility_level": "public"
                            }]
                         },
                            format="json",
                            **bearer(token))
    assert response.status_code == 400

def test_client_cannot_overwrite_private_attribute(api, user, client_app):
    grant(user, client_app[0], "gaming", "read:profile:gaming write:profile:gaming")
    token = get_token(api, client_app, user, "write:profile:gaming")
    response = api.patch(f"/api/v1/users/{user.id}/personas/gaming",
                         {
                             "attributes": [{
                                 "attribute_key": "discord_handle",
                                 "attribute_value": "X"
                            }]
                         },
                         format="json",
                         **bearer(token))
    assert response.status_code == 403

def test_owner_sees_private_attributes(api, user):
    token = login(api, user)
    response = api.get(f"/api/v1/users/{user.id}/personas/gaming", 
    **bearer(token, None))
    assert SECRETS["gaming"] in response.content.decode()