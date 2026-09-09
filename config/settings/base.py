"""Settings shared by every environment."""
import os
from pathlib import Path

import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "corsheaders",
    "rest_framework",
    "accounts", "personas", "clients", "consent", "idp", "gateway",
]
MIDDLEWARE = [
    "gateway.middleware.MaxBodySizeMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "gateway.middleware.SecurityHeadersMiddleware",
    "gateway.middleware.AuditMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = []

# ---------------------------------------------------------------- database
DATABASES = {
    "default": dj_database_url.parse(
        os.environ.get("DATABASE_URL", 
"postgres://identity:identity@127.0.0.1:5432/identity"),
        conn_max_age=0,  # serverless: never keep a connection between invocations
    )
}

DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True  # safe behind PgBouncer
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"
USE_TZ = True
STATIC_URL = "static/"

# ---------------------------------------------------------------- DRF
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser", "rest_framework.parsers.FormParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": ["gateway.authentication.BearerTokenAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["gateway.permissions.DenyByDefault"],
    "DEFAULT_THROTTLE_RATES": {"token": "30/minute", "login": "10/minute"},
    "UNAUTHENTICATED_USER": None,
    "TEST_REQUEST_DEFAULT_FORMAT": "json",
}

# ---------------------------------------------------------------- identity provider
JWT_ISSUER = os.environ.get("JWT_ISSUER", "http://localhost:8000/api/v1")
JWT_PRIVATE_KEY_B64 = os.environ.get("JWT_PRIVATE_KEY_B64", "")
JWT_KID = os.environ.get("JWT_KID", "")
CLIENT_TOKEN_LIFETIME = 3600        
# one hour (Chapter IV C)
SESSION_TOKEN_LIFETIME = 900        
# 15 minutes
REFRESH_TOKEN_LIFETIME = 7 * 24 * 3600

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"
REFRESH_COOKIE_SECURE = True

# Origins of this project's own React client
FIRST_PARTY_ORIGINS = env_list("FIRST_PARTY_ORIGINS", "http://localhost:5173")

# ---------------------------------------------------------------- CORS
CORS_ALLOWED_ORIGINS = FIRST_PARTY_ORIGINS  # registered client domains are added in gateway/cors.py
CORS_ALLOW_HEADERS = ["authorization", "content-type"]
CORS_ALLOW_METHODS = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]

# ---------------------------------------------------------------- hardening
MAX_REQUEST_BODY_BYTES = 64 * 1024
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "no-referrer"