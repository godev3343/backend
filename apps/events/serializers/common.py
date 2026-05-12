"""Общие куски сериализаторов events: brief-сериализатор Place и location-helper."""
from __future__ import annotations

from rest_framework import serializers

from apps.events.models import Event


class PlaceBriefSerializer(serializers.Serializer):
    """
    Урезанная карточка Place для nested-поля.
    Не зависим от apps.places.serializers намеренно — публичный shape
    nested-объекта в /api/events не должен меняться вслед за изменениями
    PlaceListItemSerializer.
    """

    id = serializers.IntegerField()
    name = serializers.CharField()


class LocationField(serializers.Field):
    """
    PointField → {"lat": float, "lng": float} | null.

    Используем Field (не SerializerMethodField), чтобы декларировать
    как обычное поле сериализатора и не плодить per-сериализатор
    методы-обёртки.
    """

    def to_representation(self, value):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        # PointField хранит как (x=lng, y=lat) в SRID=4326.
        return {"lat": value.y, "lng": value.x}

    def to_internal_value(self, data):  # type: ignore[no-untyped-def]
        # Read-only поле — write-флоу не нужен; админка работает напрямую с PointField.
        raise NotImplementedError("LocationField is read-only.")


def event_place_payload(event: Event) -> dict | None:
    """Хелпер для тех мест, где удобнее dict, чем nested-сериализатор."""
    if event.place_id is None:
        return None
    return {"id": event.place_id, "name": event.place.name}