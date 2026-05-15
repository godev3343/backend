"""Сериализаторы статусов."""
from __future__ import annotations

from rest_framework import serializers

from apps.gamification.services.status import Status


class UserStatusSerializer(serializers.Serializer):
    """Статус для встраивания в /api/users/me и /api/users/{id}."""

    code = serializers.CharField()
    name = serializers.CharField(source="name_ru")
    threshold = serializers.IntegerField()

    @classmethod
    def for_points(cls, points: int) -> dict:
        """Удобный шорткат для встраивания: serializer.for_points(user.points)."""
        from apps.gamification.services.status import get_status_for_points

        status = get_status_for_points(points)
        return cls(status).data