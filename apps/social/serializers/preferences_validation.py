"""
Валидация preferred_vibes и ai_context — общая для PATCH /me и PUT /preferences.
"""
from __future__ import annotations

from rest_framework import serializers

from apps.places.models import PlaceVibeTag


def validate_preferred_vibes(value: list[str]) -> list[str]:
    """
    - 0..5 элементов (size enforced в БД, тут на всякий случай).
    - Только значения из PlaceVibeTag.
    - Уникальные.
    """
    if len(value) > 5:
        raise serializers.ValidationError("Maximum 5 vibes allowed.")

    valid_tags = set(PlaceVibeTag.values)
    invalid = [v for v in value if v not in valid_tags]
    if invalid:
        raise serializers.ValidationError(
            f"Invalid vibe tag(s): {sorted(invalid)}. "
            f"Allowed: {sorted(valid_tags)}."
        )

    if len(set(value)) != len(value):
        raise serializers.ValidationError("Vibes must be unique.")

    return value