"""Чек-ины — посещения мест."""

from __future__ import annotations

from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.db import models

from apps.core.models import CreatedAtModel
from apps.places.models import Place, PlacePhoto


class CheckIn(CreatedAtModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="checkins",
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.PROTECT,
        related_name="checkins",
    )
    # Точка пользователя — может отличаться от Place.location
    location = gis_models.PointField(srid=4326)
    comment = models.CharField(max_length=500, blank=True, default="")
    photo = models.ForeignKey(
        PlacePhoto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checkins",
    )

    # Денормализация — обновляется атомарно через F() при like/unlike (EPIC 6)
    likes_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "checkins_checkin"
        indexes = [
            models.Index(fields=("user", "-created_at"), name="checkin_user_created_idx"),
            models.Index(fields=("place", "-created_at"), name="checkin_place_created_idx"),
        ]

    def __str__(self) -> str:
        return f"checkin#{self.pk} u={self.user_id} p={self.place_id}"


class Like(CreatedAtModel):
    """
    Лайк на чек-ин.

    Уникальность по (user, checkin) — гарантия "один лайк на пользователя
    на чек-ин". LikeService при IntegrityError возвращает идемпотентный 200,
    не 409 — это естественное поведение для тапа на сердечко.

    Счётчик denorm'ится в CheckIn.likes_count через F-выражение в сервисе.
    Сигналы намеренно не используем: для simple read-modify-write на одно
    поле сигналы тяжелее, чем явный update в сервисе, и сильнее запутывают
    тестирование (две точки начисления: модель и сервис).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="checkin_likes",
    )
    checkin = models.ForeignKey(
        CheckIn,
        on_delete=models.CASCADE,
        related_name="likes",
    )

    class Meta:
        db_table = "checkins_like"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "checkin"),
                name="like_unique_user_checkin",
            ),
        ]
        indexes = [
            # Для фронта: "кто лайкнул этот чек-ин" с пагинацией.
            models.Index(
                fields=("checkin", "-created_at"),
                name="like_checkin_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"like u={self.user_id} c={self.checkin_id}"
