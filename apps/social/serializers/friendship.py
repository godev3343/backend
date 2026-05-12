"""Сериализация Friendship и связанных запросов."""
from __future__ import annotations

from rest_framework import serializers


class _UserBriefSerializer(serializers.Serializer):
    """Минимальное представление юзера внутри friendship-объекта."""

    id = serializers.IntegerField()
    display_name = serializers.CharField(source="public_name", read_only=True)
    avatar_url = serializers.URLField(allow_blank=True, allow_null=True)


class IncomingFriendRequestSerializer(serializers.Serializer):
    """Заявка где request.user = to_user. Показываем from_user."""

    id = serializers.IntegerField()
    from_user = _UserBriefSerializer()
    created_at = serializers.DateTimeField()


class OutgoingFriendRequestSerializer(serializers.Serializer):
    """Заявка где request.user = from_user. Показываем to_user."""

    id = serializers.IntegerField()
    to_user = _UserBriefSerializer()
    created_at = serializers.DateTimeField()


class SendFriendRequestSerializer(serializers.Serializer):
    """POST body для отправки заявки."""

    to_user_id = serializers.IntegerField(min_value=1)


class FriendListItemSerializer(serializers.Serializer):
    """
    Элемент GET /api/friends. Это User (counterparty), не Friendship.
    """

    id = serializers.IntegerField()
    display_name = serializers.CharField(source="public_name", read_only=True)
    avatar_url = serializers.URLField(allow_blank=True, allow_null=True)
    bio = serializers.CharField(allow_blank=True)
    points = serializers.IntegerField()