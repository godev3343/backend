"""Тесты для apps.media.signals — обновление аватара после процессинга."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from apps.media.models import MediaAsset, MediaPurpose, MediaStatus
from apps.media.tests.factories import MediaAssetFactory
from apps.users.tests.factories import UserFactory


@pytest.fixture
def fake_r2_delete():
    """Мочим только delete — сигнал не делает download/upload."""
    with patch("apps.media.signals.delete_objects") as m:
        yield m


# transaction=True — нужно чтобы transaction.on_commit() сработал.
# Без этого pytest-django оборачивает тест в одну общую транзакцию,
# которая откатывается, и on_commit callbacks никогда не вызываются.
@pytest.mark.django_db(transaction=True)
class TestAvatarAssetSignal:
    def test_processed_avatar_sets_user_avatar(self, fake_r2_delete) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        asset = MediaAssetFactory(
            owner=user,
            purpose=MediaPurpose.AVATAR,
            status=MediaStatus.PENDING,
        )
        assert user.avatar_asset_id is None

        asset.status = MediaStatus.PROCESSED
        asset.save(update_fields=["status"])

        user.refresh_from_db()
        assert user.avatar_asset_id == asset.pk

    def test_processed_avatar_replaces_old(self, fake_r2_delete) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        old = MediaAssetFactory(
            owner=user,
            purpose=MediaPurpose.AVATAR,
            status=MediaStatus.PROCESSED,
            key_feed=f"avatars/{user.pk}/old/feed.webp",
            key_thumb=f"avatars/{user.pk}/old/thumb.webp",
        )
        user.avatar_asset = old
        user.save(update_fields=["avatar_asset"])

        new = MediaAssetFactory(
            owner=user,
            purpose=MediaPurpose.AVATAR,
            status=MediaStatus.PENDING,
        )
        new.status = MediaStatus.PROCESSED
        new.save(update_fields=["status"])

        user.refresh_from_db()
        assert user.avatar_asset_id == new.pk
        assert not MediaAsset.objects.filter(pk=old.pk).exists()
        fake_r2_delete.assert_called()

    def test_non_avatar_purpose_ignored(self, fake_r2_delete) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        asset = MediaAssetFactory(
            owner=user,
            purpose=MediaPurpose.CHECKIN,
            status=MediaStatus.PENDING,
        )
        asset.status = MediaStatus.PROCESSED
        asset.save(update_fields=["status"])

        user.refresh_from_db()
        assert user.avatar_asset_id is None

    def test_pending_status_ignored(self, fake_r2_delete) -> None:  # type: ignore[no-untyped-def]
        user = UserFactory()
        asset = MediaAssetFactory(
            owner=user,
            purpose=MediaPurpose.AVATAR,
            status=MediaStatus.PENDING,
            source_bytes=0,
        )
        asset.source_bytes = 12345
        asset.save(update_fields=["source_bytes"])

        user.refresh_from_db()
        assert user.avatar_asset_id is None
