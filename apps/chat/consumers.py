"""
ChatConsumer — единый per-user WebSocket (CHAT_BACKEND_SPEC §3).

Один сокет на юзера; все его переписки идут через него. На connect юзер
подписывается на группу `chat.user.{id}`; события переписки шлются в группы
обоих участников.

Client → Server:  message.send, message.read, typing
Server → Client:  message.received, message.status, typing, error

Транспорт тонкий: вся доменная логика — в ChatService (sync, оборачивается
в database_sync_to_async). Гарантированной доставки по WS не требуется —
клиент дочитывает пропущенное через REST (REST is source of truth, §3.1).
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.chat.serializers import ChatMessageSerializer
from apps.chat.services import ChatService, PresenceService
from apps.chat.services.events import (
    message_received_event,
    message_status_event,
    typing_event,
    user_group,
)
from apps.chat.services.exceptions import ChatError

logger = structlog.get_logger(__name__)

# Анти-флуд (§7, §12). Best-effort, на соединение.
_TYPING_MIN_INTERVAL = 1.5  # сек между typing одной переписки
_SEND_LIMIT = 20  # сообщений
_SEND_WINDOW = 10.0  # за столько секунд

# Код закрытия для неаутентифицированного коннекта (app-specific 4xxx).
_WS_CLOSE_UNAUTHORIZED = 4401


class ChatConsumer(AsyncJsonWebsocketConsumer):
    user: Any
    group: str

    # ---------- lifecycle --------------------------------------------------

    async def connect(self) -> None:
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=_WS_CLOSE_UNAUTHORIZED)
            return

        self.user = user
        self.group = user_group(user.pk)
        self._typing_last: dict[str, float] = {}
        self._send_times: list[float] = []

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await database_sync_to_async(PresenceService.connected)(user.pk)

        # Доставляем входящие, накопившиеся пока юзер был оффлайн, и уведомляем
        # их авторов статусом delivered.
        rows = await database_sync_to_async(ChatService.mark_pending_delivered)(user=user)
        for message_id, author_id, conversation_id in rows:
            await self.channel_layer.group_send(
                user_group(author_id),
                message_status_event(
                    conversation_id=conversation_id,
                    message_id=message_id,
                    status="delivered",
                ),
            )

    async def disconnect(self, code: int) -> None:
        if getattr(self, "user", None) is None:
            return
        await self.channel_layer.group_discard(self.group, self.channel_name)
        await database_sync_to_async(PresenceService.disconnected)(self.user.pk)

    # ---------- inbound (client → server) ----------------------------------

    async def receive_json(self, content: dict[str, Any], **kwargs: Any) -> None:
        event_type = content.get("type")
        try:
            if event_type == "message.send":
                await self._handle_send(content)
            elif event_type == "message.read":
                await self._handle_read(content)
            elif event_type == "typing":
                await self._handle_typing(content)
            # неизвестные типы молча игнорируем
        except ChatError as exc:
            await self._send_error(exc.code, exc.message)
        except Exception:
            logger.exception("chat_ws_error", event_type=event_type, user_id=self.user.pk)
            await self._send_error("internal_error", "Internal error")

    async def _handle_send(self, content: dict[str, Any]) -> None:
        client_message_id = content.get("client_message_id")
        conversation_id = content.get("conversation_id")
        text = content.get("text", "")
        if not client_message_id or not conversation_id:
            await self._send_error(
                "invalid_payload", "client_message_id and conversation_id are required"
            )
            return
        if not self._allow_send():
            await self._send_error("throttled", "Too many messages")
            return

        message, created, payload, peer_id = await self._save_message(
            conversation_id=conversation_id,
            client_message_id=client_message_id,
            text=text,
        )

        # Отправителю — sent (и на первой отправке, и на ретрае).
        await self._status_to_self(conversation_id, client_message_id, "sent")

        if created:
            # Получателю — новое сообщение.
            await self.channel_layer.group_send(
                user_group(peer_id), message_received_event(payload)
            )
            # delivered сразу, если получатель онлайн (MVP, §12).
            online = await database_sync_to_async(PresenceService.is_online)(peer_id)
            if online:
                delivered = await database_sync_to_async(ChatService.mark_delivered)(
                    message_id=message.id
                )
                if delivered:
                    await self._status_to_self(conversation_id, message.id, "delivered")
        else:
            # Ретрай существующего: догоняем отправителя актуальным статусом.
            if message.status != "sent":
                await self._status_to_self(conversation_id, message.id, message.status)

    async def _handle_read(self, content: dict[str, Any]) -> None:
        conversation_id = content.get("conversation_id")
        if not conversation_id:
            await self._send_error("invalid_payload", "conversation_id is required")
            return
        message_id = content.get("message_id")

        read_ids, peer_id = await self._mark_read(conversation_id, message_id)
        # Уведомляем автора прочитанных сообщений (в 1:1 — собеседника).
        for read_id in read_ids:
            await self.channel_layer.group_send(
                user_group(peer_id),
                message_status_event(
                    conversation_id=conversation_id,
                    message_id=read_id,
                    status="read",
                ),
            )

    async def _handle_typing(self, content: dict[str, Any]) -> None:
        conversation_id = content.get("conversation_id")
        if not conversation_id:
            return
        is_typing = bool(content.get("is_typing"))

        if is_typing and not self._allow_typing(conversation_id):
            return

        peer_id = await self._peer_for(conversation_id)
        if peer_id is None:
            return
        await self.channel_layer.group_send(
            user_group(peer_id),
            typing_event(conversation_id=conversation_id, is_typing=is_typing),
        )

    # ---------- outbound (group_send → client) -----------------------------
    # Channels маппит channel-layer `type` на эти методы (точки → подчёркивания).

    async def chat_message_received(self, event: dict[str, Any]) -> None:
        await self.send_json({"type": "message.received", "message": event["message"]})

    async def chat_message_status(self, event: dict[str, Any]) -> None:
        await self.send_json(
            {
                "type": "message.status",
                "conversation_id": event["conversation_id"],
                "message_id": event["message_id"],
                "status": event["status"],
            }
        )

    async def chat_typing(self, event: dict[str, Any]) -> None:
        await self.send_json(
            {
                "type": "typing",
                "conversation_id": event["conversation_id"],
                "is_typing": event["is_typing"],
            }
        )

    # ---------- helpers ----------------------------------------------------

    async def _status_to_self(self, conversation_id: Any, message_id: Any, status: str) -> None:
        await self.send_json(
            {
                "type": "message.status",
                "conversation_id": str(conversation_id),
                "message_id": str(message_id),
                "status": status,
            }
        )

    async def _send_error(self, code: str, detail: str) -> None:
        await self.send_json({"type": "error", "code": code, "detail": detail})

    @database_sync_to_async
    def _save_message(
        self, *, conversation_id: str, client_message_id: str, text: str
    ) -> tuple[Any, bool, dict[str, Any], int]:
        message, created = ChatService.send_message(
            sender=self.user,
            conversation_id=conversation_id,
            client_message_id=client_message_id,
            text=text,
        )
        payload = ChatMessageSerializer(message).data
        peer_id = ChatService.peer_id(message.conversation, self.user.pk)
        return message, created, payload, peer_id

    @database_sync_to_async
    def _mark_read(self, conversation_id: str, message_id: str | None) -> tuple[list[Any], int]:
        return ChatService.mark_read(
            user=self.user,
            conversation_id=conversation_id,
            message_id=message_id,
        )

    @database_sync_to_async
    def _peer_for(self, conversation_id: str) -> int | None:
        try:
            return ChatService.peer_id_for(user=self.user, conversation_id=conversation_id)
        except ChatError:
            return None

    def _allow_typing(self, conversation_id: str) -> bool:
        now = time.monotonic()
        last = self._typing_last.get(conversation_id, 0.0)
        if now - last < _TYPING_MIN_INTERVAL:
            return False
        self._typing_last[conversation_id] = now
        return True

    def _allow_send(self) -> bool:
        now = time.monotonic()
        self._send_times = [t for t in self._send_times if now - t < _SEND_WINDOW]
        if len(self._send_times) >= _SEND_LIMIT:
            return False
        self._send_times.append(now)
        return True
