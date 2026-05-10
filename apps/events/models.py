"""Городские события."""
from __future__ import annotations

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
    # Если place=None — координаты явные
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
            # Должна быть либо привязка к Place, либо явные координаты
            models.CheckConstraint(
                check=(
                    models.Q(place__isnull=False) | models.Q(location__isnull=False)
                ),
                name="event_has_place_or_location",
            ),
        ]

    def __str__(self) -> str:
        return self.title