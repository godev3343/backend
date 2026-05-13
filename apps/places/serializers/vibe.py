"""Сериализатор вайба места."""

from __future__ import annotations

from rest_framework import serializers

from apps.places.models import PlaceVibe


class PlaceVibeSerializer(serializers.ModelSerializer):
    weight = serializers.FloatField()  # из Decimal → float для JSON

    class Meta:
        model = PlaceVibe
        fields = ("tag", "weight")
