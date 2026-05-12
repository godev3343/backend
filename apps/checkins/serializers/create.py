# apps/checkins/serializers/create.py
"""Входной сериализатор для POST /api/checkins."""
from __future__ import annotations

from rest_framework import serializers


class CheckInCreateSerializer(serializers.Serializer):
    """
    Валидация входа. Бизнес-логика (дистанция, поинты) — в CheckInService.

    NB: photo_key — это key_original из MediaAsset (загружено через
    POST /api/upload/presign в EPIC 4). Опционально.
    """

    place_id = serializers.IntegerField(min_value=1)
    latitude = serializers.FloatField(min_value=-90.0, max_value=90.0)
    longitude = serializers.FloatField(min_value=-180.0, max_value=180.0)
    comment = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
    )
    photo_key = serializers.CharField(
        max_length=500,
        required=False,
        allow_null=True,
        allow_blank=False,
        default=None,
    )