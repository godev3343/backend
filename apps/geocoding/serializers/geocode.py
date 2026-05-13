"""Сериализатор результата геокодинга."""

from __future__ import annotations

from rest_framework import serializers


class GeocodeResultSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    lat = serializers.FloatField()
    lng = serializers.FloatField()
    place_type = serializers.CharField()
