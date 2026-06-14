"""
Входные сериализаторы сообщества. Только валидация — бизнес-логика в services/.

Медиа передаются КЛЮЧАМИ из media-пайплайна (presign→R2→confirm), не файлами.
Автор поста/комментария берётся из JWT, в теле его нет.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.community.models import PostMediaType

MAX_POST_TEXT = 1000
MAX_COMMENT_TEXT = 1000
MAX_MEDIA_PER_POST = 10


class PostMediaInputSerializer(serializers.Serializer):
    """Одно вложение при создании поста: тип + R2-ключ оригинала."""

    type = serializers.ChoiceField(choices=PostMediaType.choices)
    key = serializers.CharField(max_length=500)


class PostCreateSerializer(serializers.Serializer):
    """
    Тело POST /api/posts.

    Хотя бы одно из text/media должно быть непустым. media ≤ 10.
    """

    text = serializers.CharField(
        max_length=MAX_POST_TEXT,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=False,
    )
    media = PostMediaInputSerializer(many=True, required=False, default=list)

    def validate_media(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if len(value) > MAX_MEDIA_PER_POST:
            raise serializers.ValidationError(f"Too many media items (max {MAX_MEDIA_PER_POST}).")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        text = (attrs.get("text") or "").strip()
        media = attrs.get("media") or []
        if not text and not media:
            raise serializers.ValidationError(
                "Post must have non-empty text or at least one media item."
            )
        return attrs


class CommentCreateSerializer(serializers.Serializer):
    """Тело POST /api/posts/{id}/comments."""

    text = serializers.CharField(
        max_length=MAX_COMMENT_TEXT,
        allow_blank=False,
        trim_whitespace=True,
    )
