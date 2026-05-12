"""Городские события."""
from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.db import models

from apps.core.models import TimestampedModel
from apps.places.models import Place


class Event(TimestampedModel):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    place = models.ForeignKey(
        Place,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    # Денормализуется из place.location в save() — чтобы /api/events?bbox
    # фильтровал по одному GIST-индексу на event.location без JOIN на places.
    # Если place=None — location обязателен (см. CheckConstraint ниже).
    location = gis_models.PointField(srid=4326, null=True, blank=True)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    cover_url = models.URLField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_events",
    )

    class Meta:
        db_table = "events_event"
        indexes = [
            models.Index(fields=("starts_at",), name="event_starts_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(place__isnull=False) | models.Q(location__isnull=False)
                ),
                name="event_has_place_or_location",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(ends_at__isnull=True)
                    | models.Q(ends_at__gt=models.F("starts_at"))
                ),
                name="event_ends_after_starts",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        Денормализация: если событие привязано к Place — копируем place.location
        в event.location. Инвариант: для событий с place координаты === place.location;
        кастомный location актуален только когда place=None.

        Один лишний SELECT на save() — это не hot path (события создаются админом).
        """
        if self.place_id and self.place.location is not None:
            self.location = self.place.location
        super().save(*args, **kwargs)