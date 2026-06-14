"""
Генерация ключей объектов в R2.

Схема:
    {purpose}s/{owner_id}/{asset_uuid}/original.{ext}
    {purpose}s/{owner_id}/{asset_uuid}/feed.webp
    {purpose}s/{owner_id}/{asset_uuid}/thumb.webp
"""

from __future__ import annotations

import re
import uuid
from typing import Literal

from apps.media.models import MediaPurpose

CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
    "video/mp4": "mp4",
    "video/quicktime": "mov",
}

# Видео-контент: грузится тем же presign→confirm-пайплайном, но НЕ проходит
# через Pillow-обработку (см. UploadService.confirm). Постер/транскод — на
# будущее (ffmpeg в Celery), сейчас оригинал отдаётся как есть.
VIDEO_CONTENT_TYPES: frozenset[str] = frozenset({"video/mp4", "video/quicktime"})

# Назначения, ожидающие видео. Для них confirm не ставит process_image и
# сразу помечает asset PROCESSED.
VIDEO_PURPOSES: frozenset[str] = frozenset({MediaPurpose.POST_VIDEO.value})

Variant = Literal["original", "feed", "thumb"]

_SAFE_KEY_RE = re.compile(r"^[a-z0-9/_.\-]+$")


def is_supported_content_type(content_type: str) -> bool:
    return content_type in CONTENT_TYPE_TO_EXT


def is_video_content_type(content_type: str) -> bool:
    return content_type in VIDEO_CONTENT_TYPES


def is_video_purpose(purpose: str) -> bool:
    return purpose in VIDEO_PURPOSES


def content_type_matches_purpose(*, content_type: str, purpose: str) -> bool:
    """
    Видео-типы допустимы только для видео-purpose и наоборот. Защищает от
    заливки видео в avatar/checkin (Pillow упал бы) и фото в post_video.
    """
    return is_video_content_type(content_type) == is_video_purpose(purpose)


def new_asset_uuid() -> str:
    return uuid.uuid4().hex


def build_asset_prefix(*, purpose: str, owner_id: int, asset_uuid: str) -> str:
    return f"{purpose}s/{owner_id}/{asset_uuid}"


def build_original_key(
    *,
    purpose: str,
    owner_id: int,
    asset_uuid: str,
    content_type: str,
) -> str:
    ext = CONTENT_TYPE_TO_EXT[content_type]
    prefix = build_asset_prefix(purpose=purpose, owner_id=owner_id, asset_uuid=asset_uuid)
    return f"{prefix}/original.{ext}"


def build_variant_key(
    *,
    purpose: str,
    owner_id: int,
    asset_uuid: str,
    variant: Variant,
) -> str:
    prefix = build_asset_prefix(purpose=purpose, owner_id=owner_id, asset_uuid=asset_uuid)
    return f"{prefix}/{variant}.webp"


def is_safe_key(key: str) -> bool:
    return bool(_SAFE_KEY_RE.match(key)) and ".." not in key


def parse_owner_id_from_key(key: str) -> int | None:
    parts = key.split("/")
    if len(parts) < 4:
        return None
    try:
        return int(parts[1])
    except (ValueError, IndexError):
        return None


def known_purpose_from_key(key: str) -> str | None:
    parts = key.split("/")
    if not parts:
        return None
    prefix = parts[0]
    if not prefix.endswith("s"):
        return None
    purpose = prefix[:-1]
    if purpose in MediaPurpose.values:
        return purpose
    return None
