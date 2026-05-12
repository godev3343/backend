"""Сериализатор элемента афиши — GET /api/events."""
from __future__ import annotations

from rest_framework import serializers

from apps.events.serializers.common import LocationField, PlaceBriefSerializer


class EventListItemSerializer(serializers.Serializer):
    """
    Компактная карточка для ленты афиши.

    place — nested через PlaceBriefSerializer (allow_null=True).
    queryset должен идти с .select_related('place'), иначе N+1.
    """

    id = serializers.IntegerField()
    title = serializers.CharField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField(allow_null=True)
    cover_url = serializers.CharField()
    place = PlaceBriefSerializer(allow_null=True)
    location = LocationField()