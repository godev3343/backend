"""Local development."""
from .base import *  # noqa: F401,F403
from .base import LOGGING, env

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Включить SQL-логи в dev по необходимости через env
LOGGING["loggers"]["django.db.backends"]["level"] = "INFO" if env.debug else "WARNING"

# В dev ничего не отправляем в Sentry
# (sentry_init вызывается только в prod.py)