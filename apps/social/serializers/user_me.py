"""
Полный приватный профиль (/api/users/me).

Заменяет минимальный UserMeSerializer из apps/users/serializers/onboarding.py,
который использовался для ответа на онбординг в EPIC 2.
"""
from __future__ import annotations

from rest_framework import serializers


class UserMeSerializer(serializers.Serializer):
    """
    GET /api/users/me — полный приватный профиль текущего пользователя.

    friends_count / checkins_count — аннотации из queryset, не из Python.
    Source: apps.social.views.user.UserMeView собирает их через annotate().
    """

    id = serializers.IntegerField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    last_name = serializers.CharField(allow_blank=True)
    display_name = serializers.CharField(allow_blank=True)
    avatar_url = serializers.URLField(allow_blank=True)
    bio = serializers.CharField(allow_blank=True)
    points = serializers.IntegerField()
    is_email_verified = serializers.BooleanField()
    is_onboarded = serializers.BooleanField()
    friends_count = serializers.IntegerField()
    checkins_count = serializers.IntegerField()


class UserMeUpdateSerializer(serializers.Serializer):
    """
    PATCH /api/users/me — обновляемые поля.

    Email/phone/password не трогаем (это auth-флоу).
    Все поля опциональны: PATCH с одним полем должен работать.
    """

    first_name = serializers.CharField(max_length=100, min_length=1, required=False)
    last_name = serializers.CharField(
        max_length=100, allow_blank=True, required=False
    )
    display_name = serializers.CharField(
        max_length=100, min_length=2, required=False
    )
    avatar_url = serializers.URLField(allow_blank=True, required=False)
    bio = serializers.CharField(
        max_length=300, allow_blank=True, required=False
    )

    def validate(self, attrs: dict) -> dict:
        if not attrs:
            raise serializers.ValidationError(
                "At least one field must be provided."
            )
        return attrs