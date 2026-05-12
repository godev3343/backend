"""Сериализатор карточки события — GET /api/events/{id}."""
from __future__ import annotations

from rest_framework import serializers

from apps.events.serializers.list import EventListItemSerializer


class EventDetailSerializer(EventListItemSerializer):
    """List-shape + description и created_at для полной карточки."""

    description = serializers.CharField()
    created_at = serializers.DateTimeField()