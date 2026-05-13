"""Сериализатор категории места."""

from __future__ import annotations

from rest_framework import serializers

from apps.places.models import PlaceCategory


class PlaceCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaceCategory
        fields = ("slug", "name_ru", "name_kk")
