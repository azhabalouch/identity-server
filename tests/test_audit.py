"""Audit trail: allowed and denied requests both leave a row."""

import pytest

from gateway.models import AccessLog

from .conftest import bearer, get_token, grant

@pytest.mark.django_db(transaction=True)
def test_denied_request_is_logged_despite_rollback(api, user, client_app):
    grant(user, client_app[0], "gaming")
    token = get_token(api, client_app, user, "read:profile:gaming")
    AccessLog.objects.all().delete()
    response = api.get(f"/api/v1/users/{user.id}/personas/professional", **bearer(token))
    assert response.status_code == 403
    row = AccessLog.objects.get()
    assert (row.decision, row.reason, row.status_code) == ("deny", "scope mismatch", 403)
    assert row.client_id == client_app[0].client_id and row.persona_context == "gaming"

@pytest.mark.django_db
def test_allowed_request_is_logged_with_scope(api, user, client_app):
    grant(user, client_app[0], "gaming")
    token = get_token(api, client_app, user, "read:profile:gaming")
    api.get(f"/api/v1/users/{user.id}/personas/gaming", **bearer(token))
    row = AccessLog.objects.latest("id")
    assert (row.decision, row.reason, row.status_code) == ("allow", "read:profile:gaming", 200)

@pytest.mark.django_db
def test_invalid_token_is_logged_with_reason(api, user):
    api.get(f"/api/v1/users/{user.id}/personas/gaming", **bearer("bad.token.value"))
    row = AccessLog.objects.latest("id")
    assert (row.decision, row.reason, row.status_code) == ("deny", "invalid token", 401)

@pytest.mark.django_db
def test_unknown_route_is_logged_as_unhandled_denial(api):
    api.get("/api/v1/nothing-here")
    row = AccessLog.objects.latest("id")
    assert (row.decision, row.reason, row.status_code) == ("deny", "unhandled", 404)