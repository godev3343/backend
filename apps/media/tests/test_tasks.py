"""Тесты Celery-таски process_image — пайплайн с мок-R2."""

from __future__ import annotations

import io
from unittest.mock import patch

import pytest
from PIL import Image

from apps.media.models import (
    MediaAsset,
    MediaFailureReason,
    MediaStatus,
)
from apps.media.tasks import process_image
from apps.media.tests.factories import MediaAssetFactory


def _make_jpeg_bytes(width: int = 1500, height: int = 1000) -> bytes:
    img = Image.new("RGB", (width, height), color=(50, 100, 150))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


@pytest.fixture
def fake_r2():
    """In-memory R2: словарь key → bytes."""
    storage: dict[str, bytes] = {}

    def _download(key: str) -> bytes:
        from apps.media.r2 import R2ObjectNotFound

        if key not in storage:
            raise R2ObjectNotFound(f"missing {key}")
        return storage[key]

    def _upload(*, key: str, data: bytes, content_type: str, **kw) -> None:
        storage[key] = data

    def _delete_many(keys: list[str]) -> None:
        for k in keys:
            storage.pop(k, None)

    with (
        patch("apps.media.tasks.download_to_bytes", side_effect=_download),
        patch("apps.media.tasks.upload_bytes", side_effect=_upload),
        patch("apps.media.tasks.delete_objects", side_effect=_delete_many),
        patch("apps.media.signals.delete_objects", side_effect=_delete_many),
    ):
        yield storage


@pytest.mark.django_db
class TestProcessImage:
    def test_happy_path_with_downscale(self, fake_r2) -> None:  # type: ignore[no-untyped-def]
        asset = MediaAssetFactory(status=MediaStatus.PENDING)
        fake_r2[asset.key_original] = _make_jpeg_bytes(4000, 3000)

        process_image(asset.pk)

        asset.refresh_from_db()
        assert asset.status == MediaStatus.PROCESSED

        prefix = f"avatars/{asset.owner_id}/abc123"
        assert asset.key_feed == f"{prefix}/feed.webp"
        assert asset.key_thumb == f"{prefix}/thumb.webp"
        assert asset.key_original == f"{prefix}/original.webp"
        assert asset.width == 4000
        assert asset.height == 3000
        assert asset.processed_at is not None

        assert f"{prefix}/feed.webp" in fake_r2
        assert f"{prefix}/thumb.webp" in fake_r2
        assert f"{prefix}/original.webp" in fake_r2
        assert f"{prefix}/original.jpg" not in fake_r2

    def test_happy_path_no_downscale(self, fake_r2) -> None:  # type: ignore[no-untyped-def]
        asset = MediaAssetFactory(status=MediaStatus.PENDING)
        fake_r2[asset.key_original] = _make_jpeg_bytes(1500, 1000)

        process_image(asset.pk)

        asset.refresh_from_db()
        assert asset.status == MediaStatus.PROCESSED
        assert asset.key_original.endswith("/original.jpg")
        assert asset.key_original in fake_r2

    def test_idempotent_on_processed(self, fake_r2) -> None:  # type: ignore[no-untyped-def]
        asset = MediaAssetFactory(
            status=MediaStatus.PROCESSED,
            key_feed="avatars/1/abc/feed.webp",
            key_thumb="avatars/1/abc/thumb.webp",
        )

        with patch("apps.media.tasks.download_to_bytes") as dl:
            process_image(asset.pk)
            dl.assert_not_called()

    def test_source_missing_in_r2(self, fake_r2) -> None:  # type: ignore[no-untyped-def]
        asset = MediaAssetFactory(status=MediaStatus.PENDING)

        process_image(asset.pk)

        asset.refresh_from_db()
        assert asset.status == MediaStatus.FAILED
        assert asset.failure_reason == MediaFailureReason.SOURCE_MISSING

    def test_image_too_small(self, fake_r2, settings) -> None:  # type: ignore[no-untyped-def]
        settings.MEDIA_MIN_SHORT_SIDE = 400
        asset = MediaAssetFactory(status=MediaStatus.PENDING)
        fake_r2[asset.key_original] = _make_jpeg_bytes(200, 200)

        process_image(asset.pk)

        asset.refresh_from_db()
        assert asset.status == MediaStatus.FAILED
        assert asset.failure_reason == MediaFailureReason.TOO_SMALL

    def test_invalid_image_data(self, fake_r2) -> None:  # type: ignore[no-untyped-def]
        asset = MediaAssetFactory(status=MediaStatus.PENDING)
        fake_r2[asset.key_original] = b"this is not an image"

        process_image(asset.pk)

        asset.refresh_from_db()
        assert asset.status == MediaStatus.FAILED
        assert asset.failure_reason == MediaFailureReason.INVALID_FORMAT

    def test_unknown_asset_id(self, fake_r2) -> None:  # type: ignore[no-untyped-def]
        process_image(999_999)
        assert MediaAsset.objects.count() == 0
