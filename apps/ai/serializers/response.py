"""Response-сериализаторы для AI-эндпоинтов."""

from __future__ import annotations

from rest_framework import serializers


class RecommendationItemSerializer(serializers.Serializer):
    """Один элемент в ответе /api/ai/recommend."""

    place_id = serializers.IntegerField()
    name = serializers.CharField()
    reasoning = serializers.CharField()
    vibe_match = serializers.ListField(child=serializers.CharField())


class AiRecommendResponseSerializer(serializers.Serializer):
    """POST /api/ai/recommend — формат ответа."""

    items = RecommendationItemSerializer(many=True)
    request_id = serializers.IntegerField()
