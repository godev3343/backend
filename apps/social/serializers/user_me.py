# apps/social/serializers/user_me.py
"""
Полный приватный профиль (/api/users/me).

Заменяет минимальный UserMeSerializer из apps/users/serializers/onboarding.py,
который использовался для ответа на онбординг в EPIC 2.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.social.serializers.preferences_validation import validate_preferred_vibes


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
    # AI-персонализация (EPIC 8)
    preferred_vibes = serializers.ListField(
        child=serializers.CharField(), allow_empty=True
    )
    ai_context = serializers.CharField(allow_blank=True)


class UserMeUpdateSerializer(serializers.Serializer):
    """
    PATCH /api/users/me — обновляемые поля.

    Email/phone/password не трогаем (это auth-флоу).
    Аватар не принимается здесь — он грузится через /api/upload/* и
    привязывается к user.avatar_asset через media-сигнал.

    preferred_vibes/ai_context принимаем и здесь, и в PUT /api/users/me/preferences.
    Семантика разная: PATCH /me — частичный апдейт профиля целиком (юзер
    редактирует "О себе" и заодно поправил вайбы); PUT /preferences —
    атомарная замена AI-настроек (онбординг или экран "AI-предпочтения").
    """

    first_name = serializers.CharField(max_length=100, min_length=1, required=False)
    last_name = serializers.CharField(
        max_length=100, allow_blank=True, required=False
    )
    display_name = serializers.CharField(
        max_length=100, min_length=2, required=False
    )
    bio = serializers.CharField(
        max_length=300, allow_blank=True, required=False
    )
    preferred_vibes = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        max_length=5,
    )
    ai_context = serializers.CharField(
        max_length=500, allow_blank=True, required=False
    )

    def validate_preferred_vibes(self, value: list[str]) -> list[str]:
        return validate_preferred_vibes(value)

    def validate(self, attrs: dict) -> dict:
        if not attrs:
            raise serializers.ValidationError(
                "At least one field must be provided."
            )
        return attrs