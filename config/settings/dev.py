"""Local development."""
from .base import *  # noqa: F401,F403
from .base import LOGGING

DEBUG = True
ALLOWED_HOSTS = ["*"]

# SQL-логи в dev — управляются явно через env DJANGO_SQL_ECHO
import os  # noqa: E402

if os.getenv("DJANGO_SQL_ECHO", "false").lower() == "true":
    LOGGING["loggers"]["django.db.backends"]["level"] = "DEBUG"