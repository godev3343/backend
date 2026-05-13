"""Места и связанные сущности."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import CreatedAtModel, TimestampedModel


class PlaceCategory(models.Model):
    slug = models.SlugField(max_length=50, unique=True)
    name_ru = models.CharField(max_length=100)
    name_kk = models.CharField(max_length=100, blank=True, default="")

    class Meta:
        db_table = "places_category"
        verbose_name_plural = "Place categories"

    def __str__(self) -> str:
        return self.name_ru


class City(models.TextChoices):
    """
    Города, поддерживаемые приложением.
    На pre-MVP — только Астана. На Этапе 1 добавятся Алматы, Шымкент и т.д.

    Используется как фильтр в /api/places, /api/events и в AI context builder.
    Альтернатива (отдельная таблица Cities) пока избыточна — список меняется
    редко, JOIN бесполезен, фильтрация по slug достаточно эффективна с индексом.
    """

    ASTANA = "astana", "Астана"


class Place(TimestampedModel):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        PlaceCategory,
        on_delete=models.PROTECT,
        related_name="places",
    )
    location = gis_models.PointField(srid=4326, geography=False)
    address = models.CharField(max_length=300, blank=True, default="")
    phone = models.CharField(max_length=32, blank=True, default="")
    hours_json = models.JSONField(default=dict, blank=True)
    description = models.TextField(blank=True, default="")
    is_verified = models.BooleanField(default=False, db_index=True)
    city = models.CharField(
        max_length=32,
        choices=City.choices,
        default=City.ASTANA,
        db_index=True,
    )

    class Meta:
        db_table = "places_place"
        indexes = [
            # GIST индекс на PointField создаётся автоматически в PostGIS,
            # но явно прописываем — для миграции и читаемости.
            # Django GIS создаёт его через spatial_index=True (default=True).
            models.Index(fields=("category", "is_verified"), name="place_cat_verified_idx"),
        ]

    def __str__(self) -> str:
        return self.name


class PlaceVibeTag(models.TextChoices):
    CALM = "calm", "Calm"
    ACTIVE = "active", "Active"
    PRODUCTIVE = "productive", "Productive"
    ROMANTIC = "romantic", "Romantic"
    MUSICAL = "musical", "Musical"
    GAMING = "gaming", "Gaming"
    NETWORKING = "networking", "Networking"


class PlaceVibe(models.Model):
    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name="vibes",
    )
    tag = models.CharField(max_length=20, choices=PlaceVibeTag.choices)
    weight = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("1"))],
    )

    class Meta:
        db_table = "places_vibe"
        constraints = [
            models.UniqueConstraint(fields=("place", "tag"), name="placevibe_unique_pair"),
        ]
        indexes = [
            models.Index(fields=("tag",), name="placevibe_tag_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.place_id} :: {self.tag} ({self.weight})"


class PlacePhoto(CreatedAtModel):
    """
    Фотография места.
    """

    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_place_photos",
    )
    asset = models.OneToOneField(
        "media_app.MediaAsset",
        on_delete=models.CASCADE,
        related_name="place_photo",
    )

    class Meta:
        db_table = "places_photo"
        indexes = [
            models.Index(
                fields=("place", "-created_at"),
                name="placephoto_place_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"PlacePhoto#{self.pk} place={self.place_id}"