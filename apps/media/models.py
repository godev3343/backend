"""
MediaAsset — единая модель для всех загружаемых изображений.

Архитектура:
- Клиент получает presigned PUT через /api/upload/presign → загружает в R2.
- Клиент вызывает /api/upload/confirm → создаётся MediaAsset(status=PENDING)
  и ставится Celery-задача process_image.
- process_image: скачивает оригинал, генерит варианты (orig/feed/thumb),
  заливает обратно, ставит status=PROCESSED.
- Другие сущности (User.avatar_asset, PlacePhoto.asset) ссылаются на
  MediaAsset через FK.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.core.models import CreatedAtModel
from apps.media.r2 import build_public_url


class MediaPurpose(models.TextChoices):
    """
    Назначение медиа. Определяет лимиты размера и какое поле/модель
    будет ссылаться на этот asset.
    """

    AVATAR = "avatar", "Avatar"
    CHECKIN = "checkin", "Check-in photo"
    PLACE = "place", "Place photo"
    REVIEW = "review", "Review"
    POST_IMAGE = "post_image", "Community post image"
    POST_VIDEO = "post_video", "Community post video"


class MediaStatus(models.TextChoices):
    """
    Жизненный цикл asset'а.

    PENDING — клиент вызвал confirm, задача поставлена, но процессинг
              ещё не начался / не завершился.
    PROCESSED — все варианты сгенерированы и залиты, asset готов к показу.
    FAILED — процессинг упал (битый файл, слишком маленький, превышение
             retry). failure_reason содержит код причины.
    """

    PENDING = "pending", "Pending"
    PROCESSED = "processed", "Processed"
    FAILED = "failed", "Failed"


class MediaFailureReason(models.TextChoices):
    """
    Машиночитаемая причина FAILED. Используется фронтом для UI-сообщений
    и админом для разбора.
    """

    TOO_SMALL = "too_small", "Image too small"
    INVALID_FORMAT = "invalid_format", "Cannot decode image"
    SIZE_EXCEEDED = "size_exceeded", "Uploaded size exceeds limit"
    SOURCE_MISSING = "source_missing", "Original not found in R2"
    PROCESSING_ERROR = "processing_error", "Unknown processing error"


class MediaAsset(CreatedAtModel):
    """
    Загруженное изображение со всеми вариантами в R2.

    Ключи в R2 формируются по схеме (см. apps/media/services/keys.py):
        {purpose}s/{owner_id}/{asset_uuid}/{variant}.webp

    `key_original` хранится отдельно от feed/thumb потому что:
    - оригинал заливает клиент через presigned PUT, формат — то, что прислал
      (jpeg/png/heic/webp), расширение хранить НЕ обязательно — для R2
      важен ключ, не имя.
    - feed/thumb пишет воркер всегда в .webp.
    """

    # Владелец и контекст
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="media_assets",
    )
    purpose = models.CharField(
        max_length=20,
        choices=MediaPurpose.choices,
        db_index=True,
    )

    # Состояние
    status = models.CharField(
        max_length=20,
        choices=MediaStatus.choices,
        default=MediaStatus.PENDING,
        db_index=True,
    )
    failure_reason = models.CharField(
        max_length=30,
        choices=MediaFailureReason.choices,
        blank=True,
        default="",
    )

    # Ключи в R2 — относительные, без bucket и domain.
    # Public URL собирается через build_public_url().
    key_original = models.CharField(max_length=500)
    key_feed = models.CharField(max_length=500, blank=True, default="")
    key_thumb = models.CharField(max_length=500, blank=True, default="")

    # Размеры исходника (после resize, до конверсии). Нужны фронту, чтобы
    # резервировать aspect ratio в layout без CLS.
    width = models.PositiveIntegerField(default=0)
    height = models.PositiveIntegerField(default=0)

    # Размер загруженного оригинала в байтах. Заполняется после confirm
    # (head_object), нужно для аналитики и обнаружения злоупотреблений.
    source_bytes = models.PositiveIntegerField(default=0)

    # Celery task id — для отладки и возможной отмены/перезапуска.
    task_id = models.CharField(max_length=100, blank=True, default="")

    # Когда процессинг завершился (успех или фейл). null до завершения.
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "media_asset"
        indexes = [
            models.Index(
                fields=("owner", "purpose", "-created_at"),
                name="media_owner_purpose_idx",
            ),
            models.Index(
                fields=("status", "-created_at"),
                name="media_status_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"MediaAsset#{self.pk} owner={self.owner_id} purpose={self.purpose} status={self.status}"

    # ---- public URL helpers (для сериализаторов) ------------------------

    @property
    def url_original(self) -> str:
        return build_public_url(self.key_original) if self.key_original else ""

    @property
    def url_feed(self) -> str:
        # Пока процессинг не завершён — feed/thumb пусты, фронту отдаём
        # original как fallback. После PROCESSED — настоящий feed-вариант.
        if self.key_feed:
            return build_public_url(self.key_feed)
        return self.url_original

    @property
    def url_thumb(self) -> str:
        if self.key_thumb:
            return build_public_url(self.key_thumb)
        return self.url_original

    @property
    def is_ready(self) -> bool:
        return self.status == MediaStatus.PROCESSED

    def all_r2_keys(self) -> list[str]:
        """Список всех непустых R2-ключей этого asset'а — для bulk delete."""
        keys = [self.key_original]
        if self.key_feed:
            keys.append(self.key_feed)
        if self.key_thumb:
            keys.append(self.key_thumb)
        return keys
