"""
Доменные ошибки media-сервисов. Все наследуются от DomainError, чтобы
api_exception_handler сам конвертировал их в DRF-ответы с {detail, code}.
"""
from __future__ import annotations

from rest_framework import status

from apps.core.exceptions import DomainError


class MediaError(DomainError):
    """Базовая ошибка media-домена."""

    default_code = "media_error"
    default_message = "Media error."
    status_code = status.HTTP_400_BAD_REQUEST


class UnsupportedContentType(MediaError):
    default_code = "unsupported_content_type"
    default_message = "Content-Type is not supported. Allowed: jpeg, png, webp, heic."


class FileTooLarge(MediaError):
    default_code = "file_too_large"
    default_message = "Uploaded file exceeds size limit for this purpose."
    status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE


class FileTooSmall(MediaError):
    default_code = "file_too_small"
    default_message = "Uploaded file is empty or too small."


class MediaAssetNotFound(MediaError):
    default_code = "media_asset_not_found"
    default_message = "Media asset not found."
    status_code = status.HTTP_404_NOT_FOUND


class NotMediaOwner(MediaError):
    default_code = "not_media_owner"
    default_message = "You do not own this media asset."
    status_code = status.HTTP_403_FORBIDDEN


class SourceNotUploaded(MediaError):
    default_code = "source_not_uploaded"
    default_message = "Original file not found in storage. Did the upload complete?"


class SourceContentTypeMismatch(MediaError):
    default_code = "source_content_type_mismatch"
    default_message = "Uploaded file content-type does not match the requested one."
