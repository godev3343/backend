"""Test settings — отдельная БД, локи Celery."""

from .base import *
from .base import DATABASES

# Celery — eager (синхронно)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Отдельная схема не нужна — pytest-django сам создаст test_*
DATABASES["default"]["TEST"] = {"NAME": "test_aireality"}

# Быстрый хешер паролей
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
