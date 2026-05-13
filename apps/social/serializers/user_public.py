"""Публичные представления юзера (для других пользователей)."""

from __future__ import annotations

from rest_framework import serializers


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


class UserSearchResultSerializer(serializers.Serializer):
    """
    Элемент выдачи /api/users/search. Без bio/points/counts — экономим
    payload, фронту хватает avatar + name + friendship_status для кнопки.
    """

    id = serializers.IntegerField()
    display_name = serializers.CharField(source="public_name", read_only=True)
    avatar_url = serializers.URLField(allow_blank=True)
    friendship_status = serializers.CharField()
