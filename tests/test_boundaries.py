"""Architecture rules that a code review could miss."""

import ast
from pathlib import Path

import pytest
from django.urls import get_resolver
from rest_framework.throttling import ScopedRateThrottle

from gateway.permissions import AllowPublic, PersonaScopePermission, SessionPermission

from .conftest import get_token
ROOT = Path(__file__).resolve().parent.parent
APPS = ["accounts", "personas", "clients", "consent", "gateway"]

def imports_of(path):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            yield node.module, [a.name for a in node.names]
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, []

@pytest.mark.parametrize("app", APPS)
def test_only_idp_imports_the_signing_module(app):
    for path in (ROOT / app).rglob("*.py"):
        for module, names in imports_of(path):
            assert module != "idp.signing" and not (module == "idp" and "signing" in names), path

def test_every_route_has_an_explicit_permission_class():
    allowed = {AllowPublic, PersonaScopePermission, SessionPermission}
    for pattern in get_resolver().url_patterns:
        view = pattern.callback.view_class
        classes = set(view.permission_classes)
        assert classes, pattern
        if view.__module__ != "idp.views":  # token and revoke authenticate the client themselves
            assert classes <= allowed, (pattern, classes)

@pytest.mark.django_db
def test_token_endpoint_is_rate_limited(api, user, client_app, monkeypatch):
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", {"token": "3/minute", "login": "3/minute"})
    for _ in range(3):
        get_token(api, client_app, user, "read:profile:gaming")
    response = api.post("/api/v1/oauth/token", {"grant_type": "client_credentials"})
    assert response.status_code == 429