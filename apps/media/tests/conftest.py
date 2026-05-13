"""Фикстуры для media-тестов."""
from __future__ import annotations

from unittest.mock import patch

import pytest


def _fake_presign(*, key: str, content_type: str, content_length: int, ttl_seconds=None):
    return f"https://r2.test/{key}?sig=x"


def _fake_head(key: str):
    return {
        "content_length": 100_000,
        "content_type": "image/jpeg",
        "etag": "abc",
    }


@pytest.fixture
def r2_mock():
    """
    Мокаем функции R2 везде где они используются.

    Важно: патчим импорты ПО МЕСТУ использования (apps.media.services.upload),
    а не только в apps.media.r2 — иначе UploadService дёрнет оригинал.
    """
    with patch(
        "apps.media.services.upload.generate_presigned_put",
        side_effect=_fake_presign,
    ) as presign, patch(
        "apps.media.services.upload.head_object",
        side_effect=_fake_head,
    ) as head, patch(
        "apps.media.r2.upload_bytes"
    ) as upload, patch(
        "apps.media.r2.download_to_bytes",
        return_value=b"\xff\xd8\xff",
    ) as download, patch(
        "apps.media.r2.delete_object"
    ) as delete, patch(
        "apps.media.r2.delete_objects"
    ) as delete_many:
        yield {
            "presign": presign,
            "head": head,
            "upload": upload,
            "download": download,
            "delete": delete,
            "delete_many": delete_many,
        }


@pytest.fixture
def celery_eager(settings):
    """
    Заставляем Celery выполнять задачи синхронно — без брокера.
    EAGER_PROPAGATES чтобы исключения прорастали в тест, а не глотались.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    return settings