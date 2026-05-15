# apps/reviews/services/review.py
"""
ReviewService — создание / редактирование / удаление отзывов.

Поведение:
- create: один раз на (user, place). Повторно → ReviewAlreadyExists.
- update (partial): только свой отзыв. Меняет rating/text/photo.
- delete: только свой. Hard delete; ReviewLike каскадно удаляются.

Фото-флоу повторяет CheckInService: photo_key → MediaAsset → PlacePhoto
(один и тот же asset реюзается, если photo_key передан повторно).

Поинты: REVIEW_POSTED +10 при первом создании. На update — не начисляем.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404

from apps.gamification.models import PointsReason
from apps.gamification.services import PointsService
from apps.gamification.services.achievements import AchievementService
from apps.media.models import MediaAsset, MediaPurpose, MediaStatus
from apps.places.models import Place, PlacePhoto
from apps.reviews.models import Review
from apps.reviews.services.exceptions import (
    NotReviewOwner,
    PhotoNotFound,
    PhotoNotReady,
    PlaceNotFoundForReview,
    ReviewAlreadyExists,
    ReviewNotFound,
)

if TYPE_CHECKING:
    from apps.users.models import User

logger = logging.getLogger(__name__)


class ReviewService:
    """Все методы classmethod — сервис stateless."""

    @classmethod
    @transaction.atomic
    def create(
        cls,
        *,
        user: "User",
        place_id: int,
        rating: int,
        text: str = "",
        photo_key: str | None = None,
    ) -> Review:
        """
        Создать отзыв. Бросает ReviewAlreadyExists если уже был.

        Сайд-эффекты в одной транзакции:
        - PlacePhoto (если photo_key валиден)
        - PointsTransaction +10 за REVIEW_POSTED
        - AchievementService.check_for_user (trigger='review_posted')
        """
        try:
            place = Place.objects.get(pk=place_id)
        except Place.DoesNotExist as exc:
            raise PlaceNotFoundForReview() from exc

        photo = cls._resolve_photo(user=user, place=place, photo_key=photo_key)

        try:
            review = Review.objects.create(
                user=user,
                place=place,
                rating=rating,
                text=text,
                photo=photo,
            )
        except IntegrityError as exc:
            raise ReviewAlreadyExists() from exc

        PointsService.award(
            user=user,
            reason=PointsReason.REVIEW_POSTED,
            ref_type="review",
            ref_id=review.pk,
        )

        # Ачивки — побочный эффект, не должны валить создание.
        AchievementService.check_for_user(user=user, trigger="review_posted")

        return review

    @classmethod
    @transaction.atomic
    def update(
        cls,
        *,
        user: "User",
        review_id: int,
        rating: int | None = None,
        text: str | None = None,
        photo_key: str | None = None,
        clear_photo: bool = False,
    ) -> Review:
        """
        Partial update. Только свои отзывы.

        clear_photo=True означает явный сброс фото в null (PATCH с {"photo_key": null}).
        photo_key=None при clear_photo=False означает "не трогать фото".
        """
        try:
            review = Review.objects.select_for_update().get(pk=review_id)
        except Review.DoesNotExist as exc:
            raise ReviewNotFound() from exc

        if review.user_id != user.pk:
            raise NotReviewOwner()

        update_fields: list[str] = []

        if rating is not None:
            review.rating = rating
            update_fields.append("rating")

        if text is not None:
            review.text = text
            update_fields.append("text")

        if clear_photo:
            review.photo = None
            update_fields.append("photo")
        elif photo_key is not None:
            review.photo = cls._resolve_photo(
                user=user, place=review.place, photo_key=photo_key
            )
            update_fields.append("photo")

        if update_fields:
            review.save(update_fields=update_fields)

        return review

    @classmethod
    @transaction.atomic
    def delete(cls, *, user: "User", review_id: int) -> None:
        """Hard delete. Только свои отзывы."""
        try:
            review = Review.objects.get(pk=review_id)
        except Review.DoesNotExist as exc:
            raise ReviewNotFound() from exc

        if review.user_id != user.pk:
            raise NotReviewOwner()

        # PointsTransaction НЕ откатываем — это история, не текущее состояние.
        # Если потом захочется анти-абуз (создал-удалил-создал-крутит поинты),
        # доработаем в Этапе 1.
        review.delete()

    # ---- helpers --------------------------------------------------------

    @classmethod
    def _resolve_photo(
        cls,
        *,
        user: "User",
        place: Place,
        photo_key: str | None,
    ) -> PlacePhoto | None:
        """
        Найти/создать PlacePhoto по photo_key.

        Логика повторяет CheckInService._resolve_photo:
        1. None → None
        2. MediaAsset(key_original=photo_key, owner=user, purpose=REVIEW,
           status=PROCESSED). Иначе → PhotoNotFound/PhotoNotReady.
        3. PlacePhoto на этот asset уже есть (OneToOne) → переиспользуем.
        4. Иначе → create.
        """
        if photo_key is None:
            return None

        try:
            asset = MediaAsset.objects.get(
                key_original=photo_key,
                owner=user,
                purpose=MediaPurpose.REVIEW,
            )
        except MediaAsset.DoesNotExist as exc:
            raise PhotoNotFound() from exc

        if asset.status != MediaStatus.PROCESSED:
            raise PhotoNotReady()

        existing = PlacePhoto.objects.filter(asset=asset).first()
        if existing is not None:
            return existing

        return PlacePhoto.objects.create(
            place=place,
            asset=asset,
            uploaded_by=user,
        )