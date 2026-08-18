"""Production settings (Vercel)."""
from .base import *  # noqa: F401,F403
from .base import DATABASES, SECRET_KEY, env_list

if not SECRET_KEY:
  raise RuntimeError("DJANGO_SECRET_KEY is not set")

DEBUG = False
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", ".vercel.app")
DATABASES["default"].setdefault("OPTIONS", {})["sslmode"] = "require"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
REFRESH_COOKIE_SECURE = True