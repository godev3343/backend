"""Сериализаторы достижений."""
from __future__ import annotations

from rest_framework import serializers

from apps.gamification.models import Achievement, UserAchievement


class AchievementSerializer(serializers.ModelSerializer):
    """Каталог ачивок (все, что есть в системе)."""

    name = serializers.CharField(source="name_ru")
    description = serializers.CharField(source="description_ru")

    class Meta:
        model = Achievement
        fields = ("code", "name", "description", "icon_url", "order")
        read_only_fields = fields


class UserAchievementSerializer(serializers.ModelSerializer):
    """Полученная юзером ачивка с её определением."""

    achievement = AchievementSerializer(read_only=True)
    unlocked_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = UserAchievement
        fields = ("achievement", "unlocked_at")
        read_only_fields = fields