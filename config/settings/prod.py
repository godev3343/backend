"""Production."""

from __future__ import annotations

import os

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration

from .base import *  # noqa: F401,F403
from .base import env

DEBUG = False

# ---------- Hosts / proxy ----------------------------------------------------

# Railway проксирует HTTPS → HTTP внутрь контейнера. Без этого хедера
# request.is_secure() будет False и редиректы пойдут не туда.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Railway healthcheck стучится с приватного IP с Host = <публичный домен>,
# но мы добавляем wildcard на всякий + явный домен из RAILWAY_PUBLIC_DOMAIN.
_railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "").strip()
_railway_private_domain = os.environ.get("RAILWAY_PRIVATE_DOMAIN", "").strip()

ALLOWED_HOSTS = [
    ".up.railway.app",
    ".railway.app",
    "healthcheck.railway.app",
]
if _railway_domain:
    ALLOWED_HOSTS.append(_railway_domain)
if _railway_private_domain:
    ALLOWED_HOSTS.append(_railway_private_domain)

# CSRF — нужны схемы, не только хосты
CSRF_TRUSTED_ORIGINS = [
    "https://*.up.railway.app",
    "https://*.railway.app",
]
if _railway_domain:
    CSRF_TRUSTED_ORIGINS.append(f"https://{_railway_domain}")

# ---------- Security ---------------------------------------------------------

SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ---------- GeoDjango (точные пути к .so в slim-образе) ---------------------

GDAL_LIBRARY_PATH = "/usr/lib/x86_64-linux-gnu/libgdal.so.36"
GEOS_LIBRARY_PATH = "/usr/lib/x86_64-linux-gnu/libgeos_c.so.1"

# ---------- Sentry -----------------------------------------------------------

if env.sentry_dsn:
    sentry_sdk.init(
        dsn=env.sentry_dsn,
        environment=env.environment,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=0,
        profiles_sample_rate=0,
        send_default_pii=False,
    )