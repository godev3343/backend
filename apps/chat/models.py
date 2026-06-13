"""
Модели чата: 1:1 переписки, участники (read-state), сообщения.

Дизайн (CHAT_BACKEND_SPEC §1.3):
- Conversation — 1:1 переписка. Уникальность пары — через нормализованный
  ключ (user_low_id < user_high_id) + UniqueConstraint: ровно один диалог на
  пару, `get_or_create` идемпотентен и защищён от гонок на уровне БД.
- ConversationParticipant — read-state каждого участника (last_read_at) плюс
  денормализованный unread_count, чтобы GET /api/chats был O(1) без N+1 (§12).
- Message.id == client_message_id (UUID v4, генерит клиент). Это убирает
  temp→real маппинг и делает отправку идемпотентной по PK (§6).

id переписки и сообщения в JSON — строки (UUID), sender_id/peer.id — числа.
"""

from __future__ import annotations

from uuid import uuid4

from django.conf import settings
from django.db import models
from django.utils import timezone


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    # Нормализованная пара для 1:1-уникальности: всегда user_low_id < user_high_id.
    # Хранит членство денормализованно (быстрый peer без join) — read-state и
    # unread живут в ConversationParticipant.
    user_low = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )
    user_high = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )

    # Денормализация для списка чатов (§12): иначе GET /api/chats — N+1.
    last_message = models.ForeignKey(
        "Message",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Сорт списка чатов (desc). Двигаем вручную при каждом новом сообщении.
    updated_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "chat_conversation"
        constraints = [
            models.UniqueConstraint(
                fields=("user_low", "user_high"),
                name="conversation_unique_pair",
            ),
            models.CheckConstraint(
                condition=models.Q(user_low__lt=models.F("user_high")),
                name="conversation_low_lt_high",
            ),
        ]

    def __str__(self) -> str:
        return f"Conversation {self.pk}"


class ConversationParticipant(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_participations",
    )
    # Момент, до которого участник прочитал переписку. Двигается на message.read.
    last_read_at = models.DateTimeField(null=True, blank=True)
    # Денормализованный счётчик непрочитанного для этого участника (§12).
    unread_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "chat_conversation_participant"
        constraints = [
            models.UniqueConstraint(
                fields=("conversation", "user"),
                name="conversation_participant_unique",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "conversation"), name="conv_part_user_idx"),
        ]

    def __str__(self) -> str:
        return f"Participant {self.user_id} in {self.conversation_id}"


class Message(models.Model):
    # id == client_message_id (UUID v4 от клиента). Без default — клиент задаёт.
    id = models.UUIDField(primary_key=True, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="+",
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # delivered_at/read_at — серверные факты доставки/прочтения. Из них
    # вычисляется публичный status: read → delivered → sent.
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "chat_message"
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("conversation", "-created_at"),
                name="msg_conv_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"Message {self.pk} in {self.conversation_id}"

    @property
    def status(self) -> str:
        """Публичный статус сообщения (sent|delivered|read). sending/failed —
        чисто клиентские, сервер их не оперирует (§1.2)."""
        if self.read_at is not None:
            return "read"
        if self.delivered_at is not None:
            return "delivered"
        return "sent"
