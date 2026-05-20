# apps/social/serializers/user_public.py
"""Публичные представления юзера (для других пользователей)."""

from __future__ import annotations

from rest_framework import serializers
from apps.gamification.serializers.status import UserStatusSerializer


class UserPublicSerializer(serializers.Serializer):
    """
    GET /api/users/{id} — публичный профиль.

    Скрыто: email, phone, consent_at, email_verified_at, last_login, ai_context.
    ai_context — приватная подсказка для AI, не показывается чужим.
    preferred_vibes — публичны: фронт рисует ими conic-ring на аватаре.
    """

    id = serializers.IntegerField()
    display_name = serializers.CharField(source="public_name", read_only=True)
    avatar_url = serializers.URLField(allow_blank=True)
    bio = serializers.CharField(allow_blank=True)
    points = serializers.IntegerField()
    friends_count = serializers.IntegerField()
    checkins_count = serializers.IntegerField()
    preferred_vibes = serializers.ListField(
        child=serializers.CharField(), allow_empty=True,
    )
    friendship_status = serializers.CharField()
    friendship_id = serializers.IntegerField(allow_null=True)
    status = serializers.SerializerMethodField()

    def get_status(self, obj: dict) -> dict:
        return UserStatusSerializer.for_points(obj.points)


class UserSearchResultSerializer(serializers.Serializer):
    """
    Элемент выдачи /api/users/search.

    preferred_vibes сюда НЕ кладём — в поиске нужен только аватар + имя +
    кнопка. Conic-ring рисуется на странице профиля, не в списке.
    """

    id = serializers.IntegerField()
    display_name = serializers.CharField(source="public_name", read_only=True)
    avatar_url = serializers.URLField(allow_blank=True)
    friendship_status = serializers.CharField()
    friendship_id = serializers.IntegerField(allow_null=True)