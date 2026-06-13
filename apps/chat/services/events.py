"""
Конструкторы channel-layer событий + имя per-user группы.

Каждый юзер подписан на группу `chat.user.{id}`. Сервер шлёт события в группы
обоих участников переписки. `type` в channel-layer сообщении маппится Channels'ом
на метод consumer'а (точки → подчёркивания): `chat.message.received` →
`chat_message_received`. Сам consumer уже перекладывает это в клиентский конверт
(`message.received` / `message.status` / `typing`, см. §3.3).

id сущностей в события кладём строками (UUID) — как в JSON-контракте (§6).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID


def user_group(user_id: int) -> str:
    return f"chat.user.{user_id}"


def message_received_event(message: dict[str, Any]) -> dict[str, Any]:
    return {"type": "chat.message.received", "message": message}


def message_status_event(
    *, conversation_id: UUID | str, message_id: UUID | str, status: str
) -> dict[str, Any]:
    return {
        "type": "chat.message.status",
        "conversation_id": str(conversation_id),
        "message_id": str(message_id),
        "status": status,
    }


def typing_event(*, conversation_id: UUID | str, is_typing: bool) -> dict[str, Any]:
    return {
        "type": "chat.typing",
        "conversation_id": str(conversation_id),
        "is_typing": is_typing,
    }
