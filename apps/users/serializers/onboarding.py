"""Сериализатор онбординга и минимальный UserMe."""
from __future__ import annotations

from rest_framework import serializers


class OnboardingRequestSerializer(serializers.Serializer):
    """
    Заполнение профиля при первом входе.
    display_name обязателен — без него юзер считается not_onboarded.
    Аватар грузится отдельно через /api/upload/* и привязывается к
    user.avatar_asset сигналом — здесь не принимаем.
    """

    display_name = serializers.CharField(min_length=2, max_length=100)
    bio = serializers.CharField(
        required=False, allow_blank=True, max_length=300, default=""
    )
    consent = serializers.BooleanField()

    def validate_consent(self, value: bool) -> bool:
        if not value:
            raise serializers.ValidationError(
                "Consent to data processing is required."
            )
        return value


class UserMeSerializer(serializers.Serializer):
    """
    Минимальное представление текущего юзера для ответа на онбординг.
    Полный UserMeSerializer будет в EPIC 3 — пока достаточно базовых полей.
    """

    id = serializers.IntegerField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    display_name = serializers.CharField()
    avatar_url = serializers.URLField(allow_blank=True)
    bio = serializers.CharField(allow_blank=True)
    points = serializers.IntegerField()
    is_email_verified = serializers.BooleanField()
    is_onboarded = serializers.BooleanField()