"""Реэкспорт view-классов для urls.py."""

from apps.chat.views.chats import ConversationListCreateView, MessageListView

__all__ = ["ConversationListCreateView", "MessageListView"]
