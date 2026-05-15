"""Доменные ошибки reviews. Наследуются от DomainError."""
from __future__ import annotations

from apps.core.exceptions import DomainError


class ReviewError(DomainError):
    default_message = "Review error."
    default_code = "review_error"
    status_code = 400


class PlaceNotFoundForReview(ReviewError):
    default_message = "Place not found."
    default_code = "place_not_found"
    status_code = 404


class ReviewAlreadyExists(ReviewError):
    default_message = "You have already reviewed this place. Use PATCH to update."
    default_code = "review_exists"
    status_code = 409


class ReviewNotFound(ReviewError):
    default_message = "Review not found."
    default_code = "review_not_found"
    status_code = 404


class NotReviewOwner(ReviewError):
    default_message = "You can only edit/delete your own review."
    default_code = "not_review_owner"
    status_code = 403


# Photo errors — переиспользуем из checkins, чтобы не дублировать
# имена. Импорт здесь явный, чтобы вызывающий код использовал
# apps.reviews.services.exceptions единообразно.
from apps.checkins.services.exceptions import (  # noqa: E402
    PhotoNotFound,
    PhotoNotReady,
)

__all__ = (
    "NotReviewOwner",
    "PhotoNotFound",
    "PhotoNotReady",
    "PlaceNotFoundForReview",
    "ReviewAlreadyExists",
    "ReviewError",
    "ReviewNotFound",
)