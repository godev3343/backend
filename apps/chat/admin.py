"""Минимальная админка чата — для отладки. Сообщения read-only."""

from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest

from apps.chat.models import Conversation, ConversationParticipant, Message


class ParticipantInline(admin.TabularInline):
    model = ConversationParticipant
    extra = 0
    raw_id_fields = ("user",)
    readonly_fields = ("last_read_at", "unread_count")


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "user_low", "user_high", "updated_at")
    raw_id_fields = ("user_low", "user_high", "last_message")
    readonly_fields = ("created_at",)
    inlines = (ParticipantInline,)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "created_at", "status")
    raw_id_fields = ("conversation", "sender")
    readonly_fields = ("created_at", "delivered_at", "read_at")
    search_fields = ("id",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False
