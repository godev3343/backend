"""
Celery tasks для media-домена.

process_image — основная таска. Скачивает оригинал из R2, генерит варианты
через Pillow, заливает обратно, обновляет MediaAsset.

Идемпотентность:
- Если MediaAsset уже PROCESSED — выходим (повторный вызов из-за двойного
  confirm или Celery-retry на уже завершённой таске).
- Если PENDING — обрабатываем.
- Если FAILED — НЕ повторяем автоматически. Reset на pending делается
  явно через retry-endpoint (вне scope EPIC 4).

Retry:
- Только на сетевые/IO-ошибки (R2 недоступен, временный network blip).
- Не ретраим на ImageProcessingError — битый файл сам не починится.
- Ставим FAILED только когда retry исчерпан или ошибка не-ретраиабельна.
"""

from __future__ import annotations

import logging

from botocore.exceptions import BotoCoreError
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.media.models import MediaAsset, MediaFailureReason, MediaStatus
from apps.media.r2 import (
    R2Error,
    R2ObjectNotFound,
    delete_objects,
    download_to_bytes,
    upload_bytes,
)
from apps.media.services.imaging import (
    ImageProcessingError,
    ImageTooSmallError,
    process,
)
from apps.media.services.keys import build_variant_key

logger = logging.getLogger(__name__)


def _parse_asset_uuid(key_original: str) -> str:
    """{purpose}s/{owner_id}/{asset_uuid}/original.{ext} → asset_uuid."""
    return key_original.split("/")[2]


def _mark_failed(
    asset_id: int,
    reason: str,
    *,
    delete_uploaded_keys: list[str] | None = None,
) -> None:
    """
    Атомарно проставить FAILED и причину. Если уже залили какие-то
    варианты до фейла — почистим их из R2, чтобы не копились мусорные ключи.
    """
    if delete_uploaded_keys:
        try:
            delete_objects(delete_uploaded_keys)
        except R2Error:
            logger.exception("cleanup_failed_variants_failed asset_id=%s", asset_id)

    MediaAsset.objects.filter(pk=asset_id).update(
        status=MediaStatus.FAILED,
        failure_reason=reason,
        processed_at=timezone.now(),
    )


@shared_task(
    bind=True,
    queue="media",
    name="apps.media.tasks.process_image",
    max_retries=3,
    autoretry_for=(BotoCoreError, IOError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
def process_image(self, asset_id: int) -> None:  # type: ignore[no-untyped-def]
    """
    Полный pipeline обработки одного MediaAsset.

    Шаги:
    1. Загружаем asset из БД.
    2. Идемпотентный выход если уже PROCESSED.
    3. Скачиваем оригинал из R2.
    4. Прогоняем через Pillow (decode → EXIF strip → resize → WebP).
    5. Заливаем feed и thumb обратно в R2.
    6. Опционально перезаписываем оригинал в WebP (только если был resize).
    7. Обновляем MediaAsset: PROCESSED, keys, width, height, processed_at.
    """
    try:
        asset = MediaAsset.objects.get(pk=asset_id)
    except MediaAsset.DoesNotExist:
        logger.warning("process_image: asset_id=%s not found, skipping", asset_id)
        return

    if asset.status == MediaStatus.PROCESSED:
        logger.info("process_image: asset_id=%s already processed", asset_id)
        return

    purpose = asset.purpose
    owner_id = asset.owner_id
    asset_uuid = _parse_asset_uuid(asset.key_original)

    # ---- 1. download ----------------------------------------------------
    try:
        source_bytes = download_to_bytes(asset.key_original)
    except R2ObjectNotFound:
        logger.error(
            "process_image: source missing asset_id=%s key=%s",
            asset_id,
            asset.key_original,
        )
        _mark_failed(asset_id, MediaFailureReason.SOURCE_MISSING)
        return

    # ---- 2. process -----------------------------------------------------
    try:
        result = process(source_bytes, min_short_side=settings.MEDIA_MIN_SHORT_SIDE)
    except ImageTooSmallError as exc:
        logger.warning("process_image: too_small asset_id=%s err=%s", asset_id, exc)
        _mark_failed(asset_id, MediaFailureReason.TOO_SMALL)
        return
    except ImageProcessingError as exc:
        logger.warning("process_image: invalid_format asset_id=%s err=%s", asset_id, exc)
        _mark_failed(asset_id, MediaFailureReason.INVALID_FORMAT)
        return

    # ---- 3. upload variants --------------------------------------------
    feed_key = build_variant_key(
        purpose=purpose, owner_id=owner_id, asset_uuid=asset_uuid, variant="feed"
    )
    thumb_key = build_variant_key(
        purpose=purpose, owner_id=owner_id, asset_uuid=asset_uuid, variant="thumb"
    )

    # Оригинал перезаписываем в WebP только если он был downscaled.
    original_changed = (
        result.original.width != result.source_width
        or result.original.height != result.source_height
    )
    new_original_key = asset.key_original
    if original_changed:
        new_original_key = build_variant_key(
            purpose=purpose,
            owner_id=owner_id,
            asset_uuid=asset_uuid,
            variant="original",
        )

    uploaded_keys: list[str] = []
    try:
        upload_bytes(
            key=feed_key,
            data=result.feed.data,
            content_type="image/webp",
        )
        uploaded_keys.append(feed_key)

        upload_bytes(
            key=thumb_key,
            data=result.thumb.data,
            content_type="image/webp",
        )
        uploaded_keys.append(thumb_key)

        if original_changed:
            upload_bytes(
                key=new_original_key,
                data=result.original.data,
                content_type="image/webp",
            )
            uploaded_keys.append(new_original_key)
    except R2Error:
        logger.exception("process_image: r2 upload failed asset_id=%s", asset_id)
        _mark_failed(
            asset_id,
            MediaFailureReason.PROCESSING_ERROR,
            delete_uploaded_keys=uploaded_keys,
        )
        return

    # ---- 4. update asset -----------------------------------------------
    with transaction.atomic():
        updated = MediaAsset.objects.filter(pk=asset_id, status=MediaStatus.PENDING).update(
            status=MediaStatus.PROCESSED,
            key_original=new_original_key,
            key_feed=feed_key,
            key_thumb=thumb_key,
            width=result.source_width,
            height=result.source_height,
            processed_at=timezone.now(),
        )

    if updated == 0:
        # Кто-то параллельно перевёл asset в другой статус — почистим за собой
        logger.warning(
            "process_image: asset_id=%s status changed during processing, cleanup",
            asset_id,
        )
        keys_to_delete = [feed_key, thumb_key]
        if original_changed:
            keys_to_delete.append(new_original_key)
        try:
            delete_objects(keys_to_delete)
        except R2Error:
            logger.exception("cleanup after race failed asset_id=%s", asset_id)
        return

    # Если оригинал был перезаписан в WebP — удаляем исходный .jpg/.png/.heic
    if original_changed and asset.key_original != new_original_key:
        try:
            delete_objects([asset.key_original])
        except R2Error:
            # Не фейлимся — оригинал останется как мусор, потом GC-таска уберёт
            logger.warning(
                "failed to delete old original asset_id=%s key=%s",
                asset_id,
                asset.key_original,
            )

    # Сигнал post_save сработает после save(), но мы апдейтили через update()
    # — оно сигналы не триггерит. Делаем явный сигнал через save:
    MediaAsset.objects.filter(pk=asset_id).update()  # no-op чтобы не дублировать
    asset.refresh_from_db()
    # Эмитим сигнал вручную через save (только для триггера, поля уже в БД)
    from django.db.models.signals import post_save

    post_save.send(
        sender=MediaAsset,
        instance=asset,
        created=False,
        update_fields=frozenset({"status"}),
    )

    logger.info(
        "process_image done: asset_id=%s feed=%s thumb=%s",
        asset_id,
        feed_key,
        thumb_key,
    )
