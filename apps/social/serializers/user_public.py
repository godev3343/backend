"""Публичные представления юзера (для других пользователей)."""

from __future__ import annotations

from rest_framework import serializers
from apps.gamification.serializers.status import UserStatusSerializer


class UserPublicSerializer(serializers.Serializer):
    """
    GET /api/users/{id} — публичный профиль.

    Скрыто: email, phone, consent_at, email_verified_at, last_login.
    Добавлено: friendship_status (annotate в queryset).
    """

    id = serializers.IntegerField()
    display_name = serializers.CharField(source="public_name", read_only=True)
    avatar_url = serializers.URLField(allow_blank=True)
    bio = serializers.CharField(allow_blank=True)
    points = serializers.IntegerField()
    friends_count = serializers.IntegerField()
    checkins_count = serializers.IntegerField()
    friendship_status = serializers.CharField()
    status = serializers.SerializerMethodField()

    def get_status(self, obj: dict) -> dict:
        # obj — словарь с предсобранным payload в _serialize_me;
        # points там уже есть
        return UserStatusSerializer.for_points(obj.points)


class UserSearchResultSerializer(serializers.Serializer):
    """
    Элемент выдачи /api/users/search. Без bio/points/counts — экономим
    payload, фронту хватает avatar + name + friendship_status для кнопки.
    """

    id = serializers.IntegerField()
    display_name = serializers.CharField(source="public_name", read_only=True)
    avatar_url = serializers.URLField(allow_blank=True)
    friendship_status = serializers.CharField()
