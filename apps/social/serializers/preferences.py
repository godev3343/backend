"""
Сериализатор для PUT /api/users/me/preferences.

В отличие от PATCH /me, это идемпотентная полная замена AI-настроек.
Используется в онбординг-флоу и в экране "AI-предпочтения".
"""

from __future__ import annotations

from rest_framework import serializers

from apps.social.serializers.preferences_validation import validate_preferred_vibes


class UserPreferencesSerializer(serializers.Serializer):
    """
    PUT /api/users/me/preferences — атомарная замена AI-настроек.

    Оба поля required: PUT означает "вот моё новое состояние целиком".
    Если юзер хочет частично — он использует PATCH /api/users/me.

    preferred_vibes: 0..5 уникальных тегов из PlaceVibeTag.
    ai_context: 0..500 символов произвольного текста.
    """

    preferred_vibes = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=True,
        max_length=5,
    )
    ai_context = serializers.CharField(max_length=500, allow_blank=True)

    def validate_preferred_vibes(self, value: list[str]) -> list[str]:
        return validate_preferred_vibes(value)
