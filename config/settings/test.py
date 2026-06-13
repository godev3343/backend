"""Test settings — отдельная БД, локи Celery."""

from .base import *
from .base import DATABASES

# Channels — in-memory, чтобы тесты consumer'а не требовали Redis.
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Celery — eager (синхронно)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Отдельная схема не нужна — pytest-django сам создаст test_*
DATABASES["default"]["TEST"] = {"NAME": "test_aireality"}

# Быстрый хешер паролей
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Email — in-memory, чтобы mail.outbox заполнялся.
# Без этого тесты на письма с verify-кодом и password-reset токеном
# не могут извлечь тело письма.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
