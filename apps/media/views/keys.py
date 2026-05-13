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

# Допустимые MIME-типы → расширения исходника в R2.
# HEIC принимаем от iOS, конвертируем при процессинге.
CONTENT_TYPE_TO_EXT: dict[str, str] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
    "image/heif": "heif",
}

Variant = Literal["original", "feed", "thumb"]

# В ключах разрешаем только safe-символы. Это предохранитель — все наши
# generated-ключи и так safe, но если кто-то подсунет user-controlled
# input — отловим.
_SAFE_KEY_RE = re.compile(r"^[a-z0-9/_.\-]+$")


def is_supported_content_type(content_type: str) -> bool:
    return content_type in CONTENT_TYPE_TO_EXT


def new_asset_uuid() -> str:
    """uuid4 без дефисов — короче и не ломает file managers."""
    return uuid.uuid4().hex


def build_asset_prefix(*, purpose: str, owner_id: int, asset_uuid: str) -> str:
    """
    Префикс каталога asset'а. Без trailing slash.
    Пример: 'avatars/42/9c1e3a...'
    """
    return f"{purpose}s/{owner_id}/{asset_uuid}"


def build_original_key(
    *,
    purpose: str,
    owner_id: int,
    asset_uuid: str,
    content_type: str,
) -> str:
    """
    Ключ для оригинала, который зальёт клиент по presigned PUT.
    Расширение по MIME-типу — нужно чисто для читаемости в R2 UI;
    Pillow распознаёт формат по магическим байтам, расширение не использует.
    """
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
    """
    Ключ для feed/thumb-варианта. Всегда .webp — формат задаём процессором,
    не клиентом.
    """
    prefix = build_asset_prefix(purpose=purpose, owner_id=owner_id, asset_uuid=asset_uuid)
    return f"{prefix}/{variant}.webp"


def is_safe_key(key: str) -> bool:
    """
    Проверка, что ключ состоит из безопасных символов.
    Используется на confirm — клиент шлёт нам key, мы валидируем.
    """
    return bool(_SAFE_KEY_RE.match(key)) and ".." not in key


def parse_owner_id_from_key(key: str) -> int | None:
    """
    Извлечь owner_id из ключа — нужно на confirm для проверки, что юзер
    подтверждает свой ключ, а не чужой.

    Возвращает None если ключ не подходит под схему.
    """
    parts = key.split("/")
    # avatars/{owner_id}/{asset_uuid}/original.{ext}  → ≥ 4 части
    if len(parts) < 4:
        return None
    try:
        return int(parts[1])
    except (ValueError, IndexError):
        return None


def known_purpose_from_key(key: str) -> str | None:
    """Достать purpose из первого сегмента ключа ('avatars' → 'avatar')."""
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
