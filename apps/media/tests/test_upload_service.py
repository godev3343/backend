"""Тесты UploadService — бизнес-логика presign/confirm."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.conf import settings

from apps.media.models import MediaAsset, MediaPurpose, MediaStatus
from apps.media.r2 import R2ObjectNotFound
from apps.media.services.exceptions import (
    FileTooLarge,
    FileTooSmall,
    MediaAssetNotFound,
    NotMediaOwner,
    SourceContentTypeMismatch,
    SourceNotUploaded,
    UnsupportedContentType,
)
from apps.media.services.upload import UploadService
from apps.media.tests.factories import MediaAssetFactory
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestPresign:
    def test_creates_pending_asset(self, r2_mock) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        result = UploadService.presign(
            user=user,
            purpose=MediaPurpose.AVATAR,
            content_type="image/jpeg",
            content_length=50_000,
        )

        asset = MediaAsset.objects.get(pk=result.asset_id)
        assert asset.owner == user
        assert asset.purpose == MediaPurpose.AVATAR
        assert asset.status == MediaStatus.PENDING
        assert asset.key_original.startswith(f"avatars/{user.pk}/")
        assert asset.key_original.endswith("/original.jpg")
        assert asset.source_bytes == 0  # пока ничего не залито

    def test_returns_presigned_url(self, r2_mock) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        result = UploadService.presign(
            user=user,
            purpose=MediaPurpose.CHECKIN,
            content_type="image/png",
            content_length=200_000,
        )
        assert result.upload_url.startswith("https://r2.test/")
        assert result.key in result.upload_url
        assert result.expires_in == settings.UPLOAD_PRESIGN_TTL

    def test_unsupported_content_type(self, r2_mock) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        with pytest.raises(UnsupportedContentType):
            UploadService.presign(
                user=user,
                purpose=MediaPurpose.AVATAR,
                content_type="image/gif",
                content_length=1000,
            )
        # Asset не создан
        assert MediaAsset.objects.count() == 0

    def test_zero_content_length(self, r2_mock) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        with pytest.raises(FileTooSmall):
            UploadService.presign(
                user=user,
                purpose=MediaPurpose.AVATAR,
                content_type="image/jpeg",
                content_length=0,
            )

    def test_over_size_limit_avatar(self, r2_mock) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        with pytest.raises(FileTooLarge):
            UploadService.presign(
                user=user,
                purpose=MediaPurpose.AVATAR,
                content_type="image/jpeg",
                content_length=settings.UPLOAD_MAX_SIZE["avatar"] + 1,
            )
        # Asset не создан — атомарная транзакция откатилась
        assert MediaAsset.objects.count() == 0

    def test_under_avatar_but_checkin_limit_ok(self, r2_mock) -> None:  # type: ignore[no-untyped-def]
        """Avatar лимит 5 MB, checkin 20 MB — один и тот же размер по-разному."""
        user = UserFactory()
        size = 10 * 1024 * 1024  # 10 MB

        with pytest.raises(FileTooLarge):
            UploadService.presign(
                user=user,
                purpose=MediaPurpose.AVATAR,
                content_type="image/jpeg",
                content_length=size,
            )

        # А для checkin тот же размер ок
        result = UploadService.presign(
            user=user,
            purpose=MediaPurpose.CHECKIN,
            content_type="image/jpeg",
            content_length=size,
        )
        assert result.asset_id


@pytest.mark.django_db
class TestConfirm:
    def test_confirm_happy_path(self, r2_mock, celery_eager) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        asset = MediaAssetFactory(owner=user)

        # process_image — заглушка, не должна упасть
        with patch("apps.media.services.upload.process_image") as task_mock:
            task_mock.apply_async.return_value.id = "task-xyz"
            result = UploadService.confirm(user=user, asset_id=asset.pk)

        assert result.pk == asset.pk
        asset.refresh_from_db()
        assert asset.source_bytes == 100_000  # из r2_mock.head_object

    def test_confirm_unknown_asset(self, r2_mock) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        with pytest.raises(MediaAssetNotFound):
            UploadService.confirm(user=user, asset_id=999_999)

    def test_confirm_other_users_asset(self, r2_mock) -> None:  # type: ignore[no-untyped-def]
        owner = UserFactory()
        stranger = UserFactory()
        asset = MediaAssetFactory(owner=owner)

        with pytest.raises(NotMediaOwner):
            UploadService.confirm(user=stranger, asset_id=asset.pk)

    def test_confirm_source_not_uploaded(self) -> None:
        user = UserFactory()
        asset = MediaAssetFactory(owner=user)

        with patch(
            "apps.media.services.upload.head_object",
            side_effect=R2ObjectNotFound("missing"),
        ):
            with pytest.raises(SourceNotUploaded):
                UploadService.confirm(user=user, asset_id=asset.pk)

    def test_confirm_wrong_content_type_in_r2(self) -> None:
        """Клиент залил в R2 не-картинку (например, html)."""
        user = UserFactory()
        asset = MediaAssetFactory(owner=user)

        bad_head = {
            "content_length": 1000,
            "content_type": "text/html",
            "etag": "x",
        }
        with patch(
            "apps.media.services.upload.head_object", return_value=bad_head
        ):
            with pytest.raises(SourceContentTypeMismatch):
                UploadService.confirm(user=user, asset_id=asset.pk)

    def test_confirm_oversize_in_r2(self) -> None:
        """Клиент обманул при presign — на самом деле залил больше."""
        user = UserFactory()
        asset = MediaAssetFactory(owner=user, purpose=MediaPurpose.AVATAR)

        oversize = settings.UPLOAD_MAX_SIZE["avatar"] + 1
        head = {
            "content_length": oversize,
            "content_type": "image/jpeg",
            "etag": "x",
        }
        with patch(
            "apps.media.services.upload.head_object", return_value=head
        ):
            with pytest.raises(FileTooLarge):
                UploadService.confirm(user=user, asset_id=asset.pk)

    def test_confirm_idempotent_on_processed(self, r2_mock) -> None:  # type: ignore[no-untyped-def]
        """Повторный confirm на PROCESSED — no-op, без новой задачи."""
        user = UserFactory()
        asset = MediaAssetFactory(
            owner=user,
            status=MediaStatus.PROCESSED,
            source_bytes=12345,
        )

        with patch("apps.media.services.upload.process_image") as task_mock:
            UploadService.confirm(user=user, asset_id=asset.pk)

        # Задача НЕ должна была вызваться
        task_mock.apply_async.assert_not_called()

        # source_bytes не перетёрся
        asset.refresh_from_db()
        assert asset.source_bytes == 12345