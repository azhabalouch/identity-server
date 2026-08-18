"""Local development and test settings."""
from .base import *  # noqa: F401,F403
from .base import os

DEBUG = True
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "local-dev-only-not-secret")
REFRESH_COOKIE_SECURE = False