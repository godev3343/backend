"""Ошибки chat-домена. Наследуются от DomainError (см. apps/core/exceptions)."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class ChatError(DomainError):
    default_message = "Chat error."
    default_code = "chat_error"
    status_code = 400


class SelfConversationError(ChatError):
    default_message = "Cannot start a conversation with yourself."
    default_code = "self_conversation"
    status_code = 400


class NotFriends(ChatError):
    """Чат разрешён только между друзьями (взаимная дружба)."""

    default_message = "You can only chat with friends."
    default_code = "not_friends"
    status_code = 403


class TargetUserNotFound(ChatError):
    default_message = "Target user not found."
    default_code = "user_not_found"
    status_code = 404


class ConversationNotFound(ChatError):
    """Переписка не существует ИЛИ текущий юзер в ней не участник (не палим
    существование чужих переписок — 404 в обоих случаях)."""

    default_message = "Conversation not found."
    default_code = "conversation_not_found"
    status_code = 404


class MessageConflict(ChatError):
    """client_message_id уже занят сообщением в другой переписке/от другого
    отправителя — попытка переиспользовать чужой id."""

    default_message = "Message id already used."
    default_code = "message_conflict"
    status_code = 409


class EmptyMessage(ChatError):
    default_message = "Message text cannot be empty."
    default_code = "empty_message"
    status_code = 400


class MessageTooLong(ChatError):
    default_message = "Message text is too long."
    default_code = "message_too_long"
    status_code = 400
