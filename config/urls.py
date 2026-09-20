from django.urls import path

from accounts.views import RegisterView, UserDetailView
from clients.views import ClientListCreateView, ClientPublicView
from consent.views import ConsentDetailView, ConsentListCreateView
from idp.session_views import LoginView, LogoutView, RefreshView
from idp.views import JwksView, RevokeView, TokenView
from personas.views import (
    AttributeDefinitionListView,
    NameDetailView,
    NamesView,
    PersonaDetailView,
    PersonaListView,
)

urlpatterns = [
    # identity provider
    path("api/v1/oauth/token", TokenView.as_view(), name="oauth-token"),
    path("api/v1/oauth/revoke", RevokeView.as_view(), name="oauth-revoke"),
    path("api/v1/.well-known/jwks.json", JwksView.as_view(), name="jwks"),
    path("api/v1/auth/login", LoginView.as_view(), name="auth-login"),
    path("api/v1/auth/refresh", RefreshView.as_view(), name="auth-refresh"),
    path("api/v1/auth/logout", LogoutView.as_view(), name="auth-logout"),
    
    # accounts and personas
    path("api/v1/users", RegisterView.as_view(), name="users"),
    path("api/v1/users/<uuid:user_id>", UserDetailView.as_view(), name="user"),
    path("api/v1/users/<uuid:user_id>/personas", PersonaListView.as_view(), name="personas"),
    path("api/v1/users/<uuid:user_id>/personas/<str:context>", PersonaDetailView.as_view(), name="persona"),
    path("api/v1/users/<uuid:user_id>/names", NamesView.as_view(), name="names"),
    path("api/v1/users/<uuid:user_id>/names/<int:name_id>", NameDetailView.as_view(), name="name"),
    path("api/v1/attribute-definitions", AttributeDefinitionListView.as_view(), name="attribute-definitions"),

    # corporate tier
    path("api/v1/clients", ClientListCreateView.as_view(), name="clients"),
    path("api/v1/clients/<str:client_id>", ClientPublicView.as_view(), name="client"),

    # consumer tier
    path("api/v1/consents", ConsentListCreateView.as_view(), name="consents"),
    path("api/v1/consents/<uuid:grant_id>", ConsentDetailView.as_view(), name="consent"),
]