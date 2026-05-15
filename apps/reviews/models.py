"""
Отзывы на места.

Один юзер — один отзыв на одно место (UniqueConstraint).
Фото опциональное, через PlacePhoto (тот же flow что в чек-инах).
"""
from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import CreatedAtModel


class Review(CreatedAtModel):
    """
    Отзыв юзера на заведение.

    Дизайн-решение: один отзыв на пару (user, place). Хочешь изменить мнение
    — PATCH свой отзыв. Не плодим версии.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    place = models.ForeignKey(
        "places.Place",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    text = models.TextField(max_length=2000, blank=True, default="")
    # Один отзыв = один фото-asset (опционально).
    # OneToOne к PlacePhoto: фото отзыва автоматически попадает в галерею
    # места — естественный shared resource, как с чек-инами.
    photo = models.OneToOneField(
        "places.PlacePhoto",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review",
    )
    # Денормализованный счётчик — обновляется через F-выражение в ReviewLikeService.
    likes_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "reviews_review"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "place"),
                name="review_unique_per_user_place",
            ),
        ]
        indexes = [
            models.Index(
                fields=("place", "-created_at"),
                name="review_place_created_idx",
            ),
            models.Index(
                fields=("user", "-created_at"),
                name="review_user_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Review#{self.pk} u={self.user_id} p={self.place_id} r={self.rating}"


class ReviewLike(CreatedAtModel):
    """
    Лайк на отзыв.

    Отдельная модель (не generic), по аналогии с checkins.Like.
    Идемпотентность через UniqueConstraint(user, review).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="review_likes",
    )
    review = models.ForeignKey(
        Review,
        on_delete=models.CASCADE,
        related_name="likes",
    )

    class Meta:
        db_table = "reviews_review_like"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "review"),
                name="reviewlike_unique_user_review",
            ),
        ]
        indexes = [
            models.Index(
                fields=("review", "-created_at"),
                name="reviewlike_review_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"reviewlike u={self.user_id} r={self.review_id}"