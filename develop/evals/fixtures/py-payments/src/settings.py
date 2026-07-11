"""Runtime settings.

Secrets are read from the environment. Nothing secret belongs in this file.
"""
import os

SERVICE_NAME = "payments"
UPSTREAM_URL = os.environ.get("UPSTREAM_URL", "https://api.example.com")
