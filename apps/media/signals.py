# apps/media/signals.py
"""
Сигналы media-домена.

После успешного процессинга аватара автоматически обновляем
User.avatar_asset и удаляем старый asset (вместе с его R2-объектами).

Почему сигнал, а не вызов из таски:
- Логика "после PROCESSED → обновить владельца" специфична для purpose=avatar,
  и таска не должна знать про User.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.media.models import MediaAsset, MediaPurpose, MediaStatus
from apps.media.r2 import R2Error, delete_objects

logger = logging.getLogger(__name__)


@receiver(post_save, sender=MediaAsset)
def on_avatar_asset_processed(
    sender,  # type: ignore[no-untyped-def]
    instance: MediaAsset,
    created: bool,
    update_fields: frozenset[str] | None = None,
    **kwargs,  # type: ignore[no-untyped-def]
) -> None:
    """
    После PROCESSED аватара — обновляем User.avatar_asset и чистим старый.

    Реагируем ТОЛЬКО на переход в PROCESSED, смотря на update_fields.
    Это исключает срабатывание на create() в presign и на промежуточные
    update'ы source_bytes.
    """
    if created:
        return
    if instance.purpose != MediaPurpose.AVATAR:
        return
    if instance.status != MediaStatus.PROCESSED:
        return
    if update_fields is not None and "status" not in update_fields:
        return

    user = instance.owner
    old_asset_id = user.avatar_asset_id

    if old_asset_id == instance.pk:
        return  # уже привязан

    def _swap_and_cleanup() -> None:
        from apps.users.models import User  # локальный импорт против циркуляра

        User.objects.filter(pk=user.pk).update(avatar_asset_id=instance.pk)

        if old_asset_id:
            try:
                old = MediaAsset.objects.get(pk=old_asset_id)
            except MediaAsset.DoesNotExist:
                return
            _delete_asset_from_r2(old)
            old.delete()

    transaction.on_commit(_swap_and_cleanup)


def _delete_asset_from_r2(asset: MediaAsset) -> None:
    """Удалить все R2-ключи asset'а одним bulk-запросом."""
    keys = asset.all_r2_keys()
    if not keys:
        return
    try:
        delete_objects(keys)
    except R2Error:
        logger.exception("failed to cleanup old avatar asset_id=%s", asset.pk)
