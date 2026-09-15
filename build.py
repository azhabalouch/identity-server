import os
import subprocess
import sys

if os.environ.get("VERCEL_ENV") == "production":
    subprocess.run([sys.executable, "manage.py", "migrate", "--noinput"], check=True)
    subprocess.run([sys.executable, "manage.py", "sync_signing_key"], check=True)
else:
    print("Preview build: migrations skipped.")