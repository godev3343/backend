"""
Выходные сериализаторы сообщества.

Контракт под клиент `mobile/lib/features/community`:
- id поста/комментария — строка (UUID).
- author.id — числовой user id; display_name == public_name; avatar_url → '' (не null).
- счётчики денормализованы; is_liked — относительно запрашивающего юзера.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.community.models import Post, PostComment


class PostAuthorSerializer(serializers.Serializer):
    """Публичный мини-профиль автора (подмножество публичного юзера)."""

    id = serializers.IntegerField()
    display_name = serializers.CharField(source="public_name")
    avatar_url = serializers.SerializerMethodField()

    def get_avatar_url(self, obj: Any) -> str:
        asset = getattr(obj, "avatar_asset", None)
        if asset is None:
            return ""
        # url_feed — стандартный публичный URL после processing. До PROCESSED
        # отдаёт original/пусто — ответственность MediaAsset.
        return getattr(asset, "url_feed", "") or ""


class PostMediaSerializer(serializers.Serializer):
    """Вложение поста. Поля денормализованы на PostMedia при создании."""

    type = serializers.CharField()
    url = serializers.CharField()
    thumbnail_url = serializers.CharField()
    aspect_ratio = serializers.FloatField()


class PostSerializer(serializers.Serializer):
    """
    Пост ленты/детали.

    is_liked заполняется из context['liked_post_ids'] (set UUID, лайкнутых
    текущим юзером). Если контекст не передан — False (дефолт по контракту).
    media берётся из prefetched related-менеджера (ordered by position).
    """

    id = serializers.UUIDField()
    author = PostAuthorSerializer()
    text = serializers.CharField()
    media = PostMediaSerializer(many=True)
    likes_count = serializers.IntegerField()
    comments_count = serializers.IntegerField()
    shares_count = serializers.IntegerField()
    views_count = serializers.IntegerField()
    is_liked = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    def get_is_liked(self, obj: Post) -> bool:
        liked_ids: set[Any] | None = self.context.get("liked_post_ids")
        if liked_ids is None:
            return False
        return obj.id in liked_ids


class PostCommentSerializer(serializers.Serializer):
    """Плоский комментарий."""

    id = serializers.UUIDField()
    post_id = serializers.UUIDField()
    author = PostAuthorSerializer()
    text = serializers.CharField()
    likes_count = serializers.IntegerField()
    is_liked = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()

    def get_is_liked(self, obj: PostComment) -> bool:
        liked_ids: set[Any] | None = self.context.get("liked_comment_ids")
        if liked_ids is None:
            return False
        return obj.id in liked_ids
