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

    class Meta:
        db_table = "checkins_checkin"
        indexes = [
            models.Index(fields=("user", "-created_at"), name="checkin_user_created_idx"),
            models.Index(fields=("place", "-created_at"), name="checkin_place_created_idx"),
        ]

    def __str__(self) -> str:
        return f"checkin#{self.pk} u={self.user_id} p={self.place_id}"