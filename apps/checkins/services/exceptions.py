"""
Доменные ошибки для чек-инов и лайков.

Все наследуются от core.DomainError → глобальный exception_handler
превратит в Response с {detail, code, errors?}.

Конвенция (см. apps/core/exceptions.py):
- default_code, default_message — class-level атрибуты
- status_code — class-level атрибут
"""

from __future__ import annotations

from apps.core.exceptions import DomainError


class CheckInError(DomainError):
    """Базовый класс для всех ошибок этого app."""

    default_message = "Check-in error."
    default_code = "checkin_error"
    status_code = 400


class PlaceNotFoundForCheckIn(CheckInError):
    default_message = "Place not found."
    default_code = "place_not_found"
    status_code = 404


class TooFarFromPlace(CheckInError):
    """Юзер слишком далеко от заведения для чек-ина."""

    default_message = "You are too far from this place to check in."
    default_code = "too_far_from_place"
    status_code = 400


class InvalidLocation(CheckInError):
    """latitude/longitude вне допустимых диапазонов."""

    default_message = "Invalid location coordinates."
    default_code = "invalid_location"
    status_code = 400


class PhotoNotFound(CheckInError):
    """photo_key не соответствует MediaAsset юзера."""

    default_message = "Photo not found or not yet processed."
    default_code = "photo_not_found"
    status_code = 400


class PhotoNotReady(CheckInError):
    """MediaAsset существует, но ещё не PROCESSED."""

    default_message = "Photo is still being processed. Try again in a moment."
    default_code = "photo_not_ready"
    status_code = 400


class CheckInNotFound(CheckInError):
    default_message = "Check-in not found."
    default_code = "checkin_not_found"
    status_code = 404
