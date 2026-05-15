"""Сериализаторы для POST/PATCH /api/places/{id}/reviews."""
from __future__ import annotations

from rest_framework import serializers


class ReviewCreateSerializer(serializers.Serializer):
    """POST — все поля required (кроме photo_key и text)."""

    rating = serializers.IntegerField(min_value=1, max_value=5)
    text = serializers.CharField(
        max_length=2000, allow_blank=True, default=""
    )
    photo_key = serializers.CharField(
        max_length=255, allow_null=True, default=None,
    )


class ReviewUpdateSerializer(serializers.Serializer):
    """PATCH — все поля optional. photo_key=null = удалить фото."""

    rating = serializers.IntegerField(
        min_value=1, max_value=5, required=False,
    )
    text = serializers.CharField(
        max_length=2000, allow_blank=True, required=False,
    )
    # Особый случай: для отличия "не передан" от "явно null"
    # используем поле + флаг clear_photo. См. view.
    photo_key = serializers.CharField(
        max_length=255, allow_null=True, required=False,
    )

    def validate(self, attrs: dict) -> dict:
        if not attrs:
            raise serializers.ValidationError(
                "At least one field must be provided."
            )
        return attrs