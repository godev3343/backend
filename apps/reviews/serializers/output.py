"""Сериализаторы для чтения отзывов."""
from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.reviews.models import Review


class _ReviewUserMiniSerializer(serializers.Serializer):
    """Минимум данных о юзере для карточки отзыва."""

    id = serializers.IntegerField()
    public_name = serializers.CharField()
    avatar_url = serializers.CharField(allow_null=True)


class ReviewSerializer(serializers.ModelSerializer):
    """
    Сериализатор отзыва для чтения.

    is_liked возвращается из context['liked_review_ids'] — set для текущей страницы.
    Если context не выставлен (single-get без контекста) — null.
    """

    user = serializers.SerializerMethodField()
    photo_url = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = (
            "id",
            "rating",
            "text",
            "user",
            "photo_url",
            "likes_count",
            "is_liked",
            "is_mine",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_user(self, obj: Review) -> dict:
        return _ReviewUserMiniSerializer(
            {
                "id": obj.user_id,
                "public_name": obj.user.public_name,
                "avatar_url": obj.user.avatar_url,
            }
        ).data

    def get_photo_url(self, obj: Review) -> str | None:
        if obj.photo is None:
            return None
        return obj.photo.asset.url_feed

    def get_is_liked(self, obj: Review) -> bool | None:
        liked_ids = self.context.get("liked_review_ids")
        if liked_ids is None:
            return None
        return obj.id in liked_ids

    def get_is_mine(self, obj: Review) -> bool:
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return obj.user_id == request.user.pk