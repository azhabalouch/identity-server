"""Pick the settings module from the DJANGO_ENV environment variable."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Local development reads server/.env. On Vercel, variables come from the dashboard.

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

if os.environ.get("DJANGO_ENV", "local") == "production":
  from .production import *  # noqa: F401,F403
else:
  from .local import *  # noqa: F401,F403