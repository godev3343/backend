"""
Сериализаторы chat-домена (выходные — read-only).

JSON-контракт — CHAT_BACKEND_SPEC §1.1. id переписок/сообщений — строки (UUID),
sender_id/peer.id — числа. created_at/updated_at — ISO-8601 UTC.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers


class ChatParticipantSerializer(serializers.Serializer):
    """Собеседник (peer): подмножество публичного юзера + presence (§1.1)."""

    id = serializers.IntegerField(read_only=True)
    display_name = serializers.CharField(source="public_name", read_only=True)
    avatar_url = serializers.CharField(read_only=True, allow_blank=True)
    is_online = serializers.SerializerMethodField()

    def get_is_online(self, user: Any) -> bool:
        online_map: dict[int, bool] = self.context.get("online_map", {})
        return bool(online_map.get(user.pk, False))


class ChatMessageSerializer(serializers.Serializer):
    """Сообщение (§1.1). status — из delivered_at/read_at (property модели)."""

    id = serializers.UUIDField(read_only=True)
    conversation_id = serializers.UUIDField(read_only=True)
    sender_id = serializers.IntegerField(read_only=True)
    text = serializers.CharField(read_only=True, allow_blank=True)
    created_at = serializers.DateTimeField(read_only=True)
    status = serializers.CharField(read_only=True)


class ConversationSerializer(serializers.Serializer):
    """Превью переписки для списка (§1.1).

    Контекст: `viewer_id` (кто запрашивает — для вычисления peer) и
    `online_map` (presence собеседников). unread берём из аннотации
    viewer_unread (см. ChatService.list_conversations)."""

    id = serializers.UUIDField(read_only=True)
    peer = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    updated_at = serializers.DateTimeField(read_only=True)

    def get_peer(self, conversation: Any) -> dict[str, Any] | None:
        viewer_id = self.context["viewer_id"]
        # participants префетчены — без доп. запросов.
        for participant in conversation.participants.all():
            if participant.user_id != viewer_id:
                return ChatParticipantSerializer(participant.user, context=self.context).data
        return None

    def get_last_message(self, conversation: Any) -> dict[str, Any] | None:
        if conversation.last_message_id is None:
            return None
        return ChatMessageSerializer(conversation.last_message).data

    def get_unread_count(self, conversation: Any) -> int:
        return int(getattr(conversation, "viewer_unread", 0) or 0)


class CreateConversationSerializer(serializers.Serializer):
    """POST /api/chats — тело запроса (§2.3)."""

    user_id = serializers.IntegerField(min_value=1)
