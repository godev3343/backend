"""
ReviewLikeService — по аналогии с apps.checkins.services.LikeService.

Идемпотентный API:
- POST × N → один Like, счётчик +1.
- DELETE без предыдущего лайка → no-op.
"""
from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from django.db import IntegrityError, transaction
from django.db.models import F
from django.db.models.functions import Greatest

from apps.reviews.models import Review, ReviewLike
from apps.reviews.services.exceptions import ReviewNotFound

if TYPE_CHECKING:
    from apps.users.models import User


class ReviewLikeResult(str, enum.Enum):
    CREATED = "created"
    ALREADY_LIKED = "already_liked"
    REMOVED = "removed"
    WAS_NOT_LIKED = "was_not_liked"


class ReviewLikeService:
    @classmethod
    @transaction.atomic
    def like(cls, *, user: "User", review_id: int) -> str:
        if not Review.objects.filter(pk=review_id).exists():
            raise ReviewNotFound()

        try:
            with transaction.atomic():
                ReviewLike.objects.create(user=user, review_id=review_id)
        except IntegrityError:
            return ReviewLikeResult.ALREADY_LIKED

        Review.objects.filter(pk=review_id).update(
            likes_count=F("likes_count") + 1
        )
        return ReviewLikeResult.CREATED

    @classmethod
    @transaction.atomic
    def unlike(cls, *, user: "User", review_id: int) -> str:
        if not Review.objects.filter(pk=review_id).exists():
            raise ReviewNotFound()

        deleted, _ = ReviewLike.objects.filter(
            user=user, review_id=review_id
        ).delete()

        if deleted == 0:
            return ReviewLikeResult.WAS_NOT_LIKED

        Review.objects.filter(pk=review_id).update(
            likes_count=Greatest(F("likes_count") - 1, 0)
        )
        return ReviewLikeResult.REMOVED