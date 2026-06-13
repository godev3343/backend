"""
ChatService — бизнес-логика чата (всё, что не транспорт).

Stateless, методы classmethod/staticmethod (как FriendshipService).
Транспорт (WS-рассылка, REST-сериализация) — снаружи, в consumer/views.

Идемпотентность и денормализация (см. CHAT_BACKEND_SPEC §6, §12):
- get_or_create_conversation — один диалог на пару, защита от гонок через
  UniqueConstraint(user_low, user_high).
- send_message — get_or_create(id=client_message_id): ретрай после обрыва
  не дублирует. В той же транзакции двигаем Conversation.last_message/
  updated_at и инкрементим unread_count получателю.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, OuterRef, QuerySet, Subquery
from django.utils import timezone

from apps.chat.models import Conversation, ConversationParticipant, Message
from apps.chat.services.exceptions import (
    ConversationNotFound,
    EmptyMessage,
    MessageConflict,
    MessageTooLong,
    NotFriends,
    SelfConversationError,
    TargetUserNotFound,
)
from apps.social.services import FriendshipService

if TYPE_CHECKING:
    from apps.users.models import User as UserType

User = get_user_model()

# Лимит длины сообщения (§7). Enforce на бэке, не только на клиенте.
MAX_TEXT_LENGTH = 4000


class ChatService:
    # ---------- conversations ---------------------------------------------

    @staticmethod
    def _ordered_pair(uid_a: int, uid_b: int) -> tuple[int, int]:
        """Нормализованная пара (low, high) для ключа 1:1-переписки."""
        return (uid_a, uid_b) if uid_a < uid_b else (uid_b, uid_a)

    @classmethod
    @transaction.atomic
    def get_or_create_conversation(
        cls, *, user: UserType, peer_id: int
    ) -> tuple[Conversation, bool]:
        """
        Найти/создать 1:1-переписку user↔peer. Идемпотентно.

        Бросает SelfConversationError / TargetUserNotFound / NotFriends.
        """
        if user.pk == peer_id:
            raise SelfConversationError()

        if not User.objects.filter(pk=peer_id, is_active=True).exists():
            raise TargetUserNotFound()

        # Чат только между друзьями (§7).
        if not FriendshipService.is_friends(user_a_id=user.pk, user_b_id=peer_id):
            raise NotFriends()

        low_id, high_id = cls._ordered_pair(user.pk, peer_id)
        conversation, created = Conversation.objects.get_or_create(
            user_low_id=low_id,
            user_high_id=high_id,
            defaults={"updated_at": timezone.now()},
        )
        if created:
            ConversationParticipant.objects.bulk_create(
                [
                    ConversationParticipant(conversation=conversation, user_id=low_id),
                    ConversationParticipant(conversation=conversation, user_id=high_id),
                ]
            )
        return conversation, created

    @classmethod
    def list_conversations(cls, *, user: UserType) -> QuerySet[Conversation]:
        """
        Переписки user, сорт по updated_at desc. Аннотирует viewer_unread
        (непрочитанное текущим юзером) одним коррелированным Subquery и
        префетчит участников/last_message — для O(1) сериализации без N+1.
        """
        my_participant = ConversationParticipant.objects.filter(
            conversation=OuterRef("pk"), user=user
        )
        return (
            Conversation.objects.filter(participants__user=user)
            .annotate(viewer_unread=Subquery(my_participant.values("unread_count")[:1]))
            .select_related("last_message", "last_message__sender")
            .prefetch_related("participants__user__avatar_asset")
            .order_by("-updated_at", "-created_at")
            .distinct()
        )

    # ---------- messages ---------------------------------------------------

    @staticmethod
    def _get_participant_or_raise(
        *, user: UserType, conversation_id: UUID | str
    ) -> ConversationParticipant:
        """Участие текущего юзера в переписке. Нет участия/переписки →
        ConversationNotFound (404, без утечки существования чужих чатов)."""
        try:
            return ConversationParticipant.objects.select_related("conversation").get(
                conversation_id=conversation_id, user=user
            )
        except ConversationParticipant.DoesNotExist as exc:
            raise ConversationNotFound() from exc

    @classmethod
    def get_messages(cls, *, user: UserType, conversation_id: UUID | str) -> QuerySet[Message]:
        """История переписки, новые первыми (desc). Только участнику."""
        cls._get_participant_or_raise(user=user, conversation_id=conversation_id)
        return (
            Message.objects.filter(conversation_id=conversation_id)
            .select_related("sender")
            .order_by("-created_at")
        )

    @classmethod
    @transaction.atomic
    def send_message(
        cls,
        *,
        sender: UserType,
        conversation_id: UUID | str,
        client_message_id: UUID | str,
        text: str,
    ) -> tuple[Message, bool]:
        """
        Сохранить сообщение. Идемпотентно по client_message_id (== Message.id).

        Возвращает (message, created). created=False — это ретрай, дубль не
        создан. При created=True двигает denорм last_message/updated_at и
        инкрементит unread получателю в той же транзакции.
        """
        text = (text or "").strip()
        if not text:
            raise EmptyMessage()
        if len(text) > MAX_TEXT_LENGTH:
            raise MessageTooLong()

        participant = cls._get_participant_or_raise(user=sender, conversation_id=conversation_id)
        conversation = participant.conversation

        message, created = Message.objects.get_or_create(
            id=client_message_id,
            defaults={"conversation": conversation, "sender": sender, "text": text},
        )
        if not created:
            # Ретрай по PK. Сообщение обязано принадлежать тому же отправителю
            # и переписке — иначе попытка занять чужой id.
            if message.conversation_id != conversation.id or message.sender_id != sender.pk:
                raise MessageConflict()
            return message, False

        Conversation.objects.filter(pk=conversation.pk).update(
            last_message=message, updated_at=message.created_at
        )
        ConversationParticipant.objects.filter(conversation=conversation).exclude(
            user=sender
        ).update(unread_count=F("unread_count") + 1)
        return message, True

    @staticmethod
    def mark_delivered(*, message_id: UUID | str) -> bool:
        """Проставить delivered_at (если ещё не стоит). True — если изменили."""
        return (
            Message.objects.filter(id=message_id, delivered_at__isnull=True).update(
                delivered_at=timezone.now()
            )
            > 0
        )

    @classmethod
    @transaction.atomic
    def mark_pending_delivered(cls, *, user: UserType) -> list[tuple[UUID, int, UUID]]:
        """
        На (ре)коннекте: проставить delivered всем недоставленным входящим
        сообщениям user. Возвращает [(message_id, author_id, conversation_id)]
        — consumer уведомит авторов статусом delivered.
        """
        rows = list(
            Message.objects.filter(delivered_at__isnull=True)
            .filter(conversation__participants__user=user)
            .exclude(sender=user)
            .values_list("id", "sender_id", "conversation_id")
        )
        if rows:
            Message.objects.filter(id__in=[r[0] for r in rows]).update(delivered_at=timezone.now())
        return rows

    @classmethod
    @transaction.atomic
    def mark_read(
        cls,
        *,
        user: UserType,
        conversation_id: UUID | str,
        message_id: UUID | str | None = None,
    ) -> tuple[list[UUID], int]:
        """
        Отметить входящие прочитанными до message_id включительно (или все,
        если message_id не задан/не найден). Двигает last_read_at, обнуляет
        unread_count. Возвращает (read_message_ids, peer_id) — consumer
        уведомит автора статусом read.
        """
        participant = cls._get_participant_or_raise(user=user, conversation_id=conversation_id)
        peer_id = cls.peer_id(participant.conversation, user.pk)
        now = timezone.now()

        unread = (
            Message.objects.filter(conversation_id=conversation_id)
            .exclude(sender=user)
            .filter(read_at__isnull=True)
        )
        if message_id is not None:
            boundary = (
                Message.objects.filter(id=message_id, conversation_id=conversation_id)
                .values_list("created_at", flat=True)
                .first()
            )
            if boundary is not None:
                unread = unread.filter(created_at__lte=boundary)

        read_ids = list(unread.values_list("id", flat=True))
        if read_ids:
            Message.objects.filter(id__in=read_ids).update(read_at=now)

        ConversationParticipant.objects.filter(conversation_id=conversation_id, user=user).update(
            last_read_at=now, unread_count=0
        )
        return read_ids, peer_id

    # ---------- routing helpers -------------------------------------------

    @staticmethod
    def peer_id(conversation: Conversation, user_id: int) -> int:
        """id собеседника в 1:1 (по денорм. user_low/user_high — без запроса)."""
        if conversation.user_low_id == user_id:
            return conversation.user_high_id
        return conversation.user_low_id

    @classmethod
    def peer_id_for(cls, *, user: UserType, conversation_id: UUID | str) -> int:
        """peer_id с проверкой участия. Бросает ConversationNotFound."""
        participant = cls._get_participant_or_raise(user=user, conversation_id=conversation_id)
        return cls.peer_id(participant.conversation, user.pk)
