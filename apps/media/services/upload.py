"""
UploadService — двухэтапная загрузка через presigned PUT.

Флоу:
1) presign(user, purpose, content_type, content_length)
   - Валидируем purpose / content-type / лимит размера
   - Генерим MediaAsset(status=PENDING, key_original=...)
   - Возвращаем presigned PUT URL + key для клиента

2) Клиент льёт файл прямо в R2 по этому URL (мимо нашего бэкенда).

3) confirm(user, asset_id)
   - HEAD на R2: проверяем что файл реально загрузился
   - Сверяем content-type и size с тем, что было заявлено на presign
   - Ставим Celery-таску process_image
   - Возвращаем MediaAsset (всё ещё PENDING, но source_bytes уже проставлен)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import transaction

from apps.media.models import MediaAsset, MediaStatus
from apps.media.r2 import (
    R2ObjectNotFound,
    generate_presigned_put,
    head_object,
)
from apps.media.services.exceptions import (
    FileTooLarge,
    FileTooSmall,
    MediaAssetNotFound,
    NotMediaOwner,
    SourceContentTypeMismatch,
    SourceNotUploaded,
    UnsupportedContentType,
)
from apps.media.services.keys import (
    build_original_key,
    is_supported_content_type,
    new_asset_uuid,
)
from apps.media.tasks import process_image

if TYPE_CHECKING:
    from apps.users.models import User

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PresignResult:
    """Результат presign — то, что отдаём фронту."""

    asset_id: int
    upload_url: str
    key: str
    expires_in: int


class UploadService:
    """Все методы classmethod — сервис stateless."""

    # ---- helpers --------------------------------------------------------

    @staticmethod
    def _max_size(purpose: str) -> int:
        try:
            return settings.UPLOAD_MAX_SIZE[purpose]
        except KeyError as exc:
            # purpose уже провалидирован сериализатором, но на всякий случай
            raise UnsupportedContentType() from exc

    # ---- presign --------------------------------------------------------

    @classmethod
    @transaction.atomic
    def presign(
        cls,
        *,
        user: User,
        purpose: str,
        content_type: str,
        content_length: int,
    ) -> PresignResult:
        """
        Выдать presigned PUT URL для прямой загрузки.

        Raises:
            UnsupportedContentType — Content-Type не в whitelist
            FileTooLarge — превышен лимит для purpose
            FileTooSmall — Content-Length <= 0
        """
        if not is_supported_content_type(content_type):
            raise UnsupportedContentType()

        if content_length <= 0:
            raise FileTooSmall()

        max_size = cls._max_size(purpose)
        if content_length > max_size:
            raise FileTooLarge(
                message=(
                    f"File size {content_length} exceeds limit {max_size} for purpose '{purpose}'."
                )
            )

        asset_uuid = new_asset_uuid()
        key = build_original_key(
            purpose=purpose,
            owner_id=user.pk,
            asset_uuid=asset_uuid,
            content_type=content_type,
        )

        # Создаём MediaAsset в БД ДО presign. Если presign упадёт —
        # транзакция откатится, asset не остаётся "висеть".
        asset = MediaAsset.objects.create(
            owner=user,
            purpose=purpose,
            status=MediaStatus.PENDING,
            key_original=key,
            source_bytes=0,  # фактический размер узнаем на confirm
        )

        upload_url = generate_presigned_put(
            key=key,
            content_type=content_type,
            content_length=content_length,
            ttl_seconds=settings.UPLOAD_PRESIGN_TTL,
        )

        logger.info(
            "presign issued: asset_id=%s user_id=%s purpose=%s size=%d key=%s",
            asset.pk,
            user.pk,
            purpose,
            content_length,
            key,
        )

        return PresignResult(
            asset_id=asset.pk,
            upload_url=upload_url,
            key=key,
            expires_in=settings.UPLOAD_PRESIGN_TTL,
        )

    # ---- confirm --------------------------------------------------------

    @classmethod
    @transaction.atomic
    def confirm(cls, *, user: User, asset_id: int) -> MediaAsset:
        """
        Подтвердить что клиент закончил загрузку.
        HEAD-ом проверяем что объект в R2 есть, ставим Celery-задачу.

        Idempotent: повторный confirm на уже PROCESSED — возвращает asset
        без повторной задачи. Повторный confirm на PENDING со свежей task_id
        — тоже no-op (защита от двойного клика на фронте).

        Raises:
            MediaAssetNotFound — нет asset с таким id
            NotMediaOwner — asset принадлежит другому юзеру
            SourceNotUploaded — в R2 по ключу пусто
            FileTooLarge — фактический размер больше лимита
            SourceContentTypeMismatch — content-type в R2 не из whitelist
        """
        try:
            asset = MediaAsset.objects.select_for_update().get(pk=asset_id)
        except MediaAsset.DoesNotExist as exc:
            raise MediaAssetNotFound() from exc

        if asset.owner_id != user.pk:
            raise NotMediaOwner()

        # Идемпотентность: уже обработан → просто возвращаем
        if asset.status == MediaStatus.PROCESSED:
            return asset

        # HEAD R2 — проверяем что клиент реально залил файл
        try:
            head = head_object(asset.key_original)
        except R2ObjectNotFound as exc:
            raise SourceNotUploaded() from exc

        content_type = str(head["content_type"])
        content_length = int(head["content_length"])

        if not is_supported_content_type(content_type):
            raise SourceContentTypeMismatch(
                message=(f"Uploaded content-type '{content_type}' is not supported.")
            )

        max_size = cls._max_size(asset.purpose)
        if content_length > max_size:
            raise FileTooLarge(
                message=(f"Uploaded file size {content_length} exceeds limit {max_size}.")
            )

        asset.source_bytes = content_length
        # task_id выставит задача (process_image) — здесь только обновим
        # source_bytes и оставим PENDING.
        asset.save(update_fields=["source_bytes"])

        # Ставим задачу. apply_async вернёт AsyncResult, оттуда возьмём id.
        # transaction.on_commit гарантирует, что задача стартанёт ТОЛЬКО
        # после успешного коммита транзакции — иначе воркер может схватить
        # asset раньше, чем он закоммитится в БД.
        def _enqueue() -> None:
            result = process_image.apply_async(args=[asset.pk], queue="media")
            # Записываем task_id уже вне select_for_update-транзакции
            MediaAsset.objects.filter(pk=asset.pk).update(task_id=result.id)

        transaction.on_commit(_enqueue)

        logger.info(
            "confirm accepted: asset_id=%s size=%d type=%s",
            asset.pk,
            content_length,
            content_type,
        )

        return asset
