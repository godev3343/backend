"""Local development."""
from .base import *  # noqa: F401,F403
from .base import LOGGING

DEBUG = True
ALLOWED_HOSTS = ["*"]

# SQL-логи в dev — управляются явно через env DJANGO_SQL_ECHO
import os  # noqa: E402

if os.getenv("DJANGO_SQL_ECHO", "false").lower() == "true":
    LOGGING["loggers"]["django.db.backends"]["level"] = "DEBUG# config/settings/dev.py"
"""Local development."""
import os

from .base import *  # noqa: F401,F403
from .base import LOGGING

DEBUG = True
ALLOWED_HOSTS = ["*"]

# SQL-логи в dev — управляются явно через env DJANGO_SQL_ECHO
if os.getenv("DJANGO_SQL_ECHO", "false").lower() == "true":
    LOGGING["loggers"]["django.db.backends"]["level"] = "DEBUG"

# Email в dev: по умолчанию в консоль, чтобы не тратить квоту Gmail
# на отладочные регистрации. Чтобы реально слать письма из дева —
# в .env поставь DJANGO_EMAIL_REAL=true.
if os.getenv("DJANGO_EMAIL_REAL", "false").lower() != "true":
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"