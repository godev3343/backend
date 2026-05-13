"""Request-сериализаторы для AI-эндпоинтов."""

from __future__ import annotations

from rest_framework import serializers


class AiRecommendRequestSerializer(serializers.Serializer):
    """POST /api/ai/recommend — тело запроса."""

    query = serializers.CharField(min_length=3, max_length=500)
