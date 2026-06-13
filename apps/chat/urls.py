"""Чат: список переписок, история сообщений. Пути без trailing slash."""

from __future__ import annotations

from django.urls import path

from apps.chat.views import ConversationListCreateView, MessageListView

app_name = "chat"

urlpatterns = [
    path("chats", ConversationListCreateView.as_view(), name="conversation_list"),
    path(
        "chats/<uuid:conversation_id>/messages",
        MessageListView.as_view(),
        name="conversation_messages",
    ),
]
