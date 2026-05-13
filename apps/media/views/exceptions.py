"""
Доменные ошибки media-сервисов. Все наследуются от DomainError, чтобы
api_exception_handler сам конвертировал их в DRF-ответы с {detail, code}.
"""

from __future__ import annotations

from rest_framework import status

from apps.core.exceptions import DomainError


class MediaError(DomainError):
    """Базовая ошибка media-домена."""

    code = "media_error"
    status_code = status.HTTP_400_BAD_REQUEST


class UnsupportedContentType(MediaError):
    code = "unsupported_content_type"
    message = "Content-Type is not supported. Allowed: jpeg, png, webp, heic."


class FileTooLarge(MediaError):
    code = "file_too_large"
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    message = "Uploaded file exceeds size limit for this purpose."


class FileTooSmall(MediaError):
    """Минимальный размер файла (от 1 байта) — не путать с image dimensions."""

    code = "file_too_small"
    message = "Uploaded file is empty or too small."


class MediaAssetNotFound(MediaError):
    code = "media_asset_not_found"
    status_code = status.HTTP_404_NOT_FOUND
    message = "Media asset not found."


class NotMediaOwner(MediaError):
    """Confirm/удаление чужого asset'а."""

    code = "not_media_owner"
    status_code = status.HTTP_403_FORBIDDEN
    message = "You do not own this media asset."


class SourceNotUploaded(MediaError):
    """Confirm вызван, но в R2 по ключу ничего нет."""

    code = "source_not_uploaded"
    message = "Original file not found in storage. Did the upload complete?"


class SourceContentTypeMismatch(MediaError):
    """В R2 лежит файл с не тем Content-Type, что заявили при presign."""

    code = "source_content_type_mismatch"
    message = "Uploaded file content-type does not match the requested one."
