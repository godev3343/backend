# config/settings/prod.py
"""Production."""

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *
from .base import env

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
GDAL_LIBRARY_PATH = "/usr/lib/x86_64-linux-gnu/libgdal.so.36"
GEOS_LIBRARY_PATH = "/usr/lib/x86_64-linux-gnu/libgeos_c.so.1"


if env.sentry_dsn:
    sentry_sdk.init(
        dsn=env.sentry_dsn,
        environment=env.environment,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0,
        profiles_sample_rate=0,
        send_default_pii=False,
    )
