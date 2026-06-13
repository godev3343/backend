"""Юнит-тесты ChatService — доменная логика чата."""

from __future__ import annotations

from uuid import uuid4

import pytest

from apps.chat.models import Conversation, ConversationParticipant, Message
from apps.chat.services import ChatService
from apps.chat.services.exceptions import (
    ConversationNotFound,
    EmptyMessage,
    MessageConflict,
    MessageTooLong,
    NotFriends,
    SelfConversationError,
    TargetUserNotFound,
)
from apps.chat.tests.factories import make_friends, onboarded_user


def _pair():  # type: ignore[no-untyped-def]
    a = onboarded_user(display_name="a")
    b = onboarded_user(display_name="b")
    make_friends(a, b)
    return a, b


def _conversation(a, b):  # type: ignore[no-untyped-def]
    conv, _ = ChatService.get_or_create_conversation(user=a, peer_id=b.pk)
    return conv


@pytest.mark.django_db
class TestGetOrCreateConversation:
    def test_creates_with_two_participants(self) -> None:
        a, b = _pair()
        conv, created = ChatService.get_or_create_conversation(user=a, peer_id=b.pk)
        assert created is True
        assert conv.user_low_id == min(a.pk, b.pk)
        assert conv.user_high_id == max(a.pk, b.pk)
        assert conv.participants.count() == 2

    def test_idempotent_either_direction(self) -> None:
        a, b = _pair()
        c1, created1 = ChatService.get_or_create_conversation(user=a, peer_id=b.pk)
        c2, created2 = ChatService.get_or_create_conversation(user=b, peer_id=a.pk)
        assert c1.pk == c2.pk
        assert created1 is True
        assert created2 is False
        assert Conversation.objects.count() == 1

    def test_non_friend_forbidden(self) -> None:
        a = onboarded_user(display_name="a")
        b = onboarded_user(display_name="b")  # не друзья
        with pytest.raises(NotFriends):
            ChatService.get_or_create_conversation(user=a, peer_id=b.pk)

    def test_self_rejected(self) -> None:
        a = onboarded_user()
        with pytest.raises(SelfConversationError):
            ChatService.get_or_create_conversation(user=a, peer_id=a.pk)

    def test_unknown_peer(self) -> None:
        a = onboarded_user()
        with pytest.raises(TargetUserNotFound):
            ChatService.get_or_create_conversation(user=a, peer_id=999_999)


@pytest.mark.django_db
class TestSendMessage:
    def test_creates_and_denormalizes(self) -> None:
        a, b = _pair()
        conv = _conversation(a, b)
        mid = uuid4()
        message, created = ChatService.send_message(
            sender=a, conversation_id=conv.id, client_message_id=mid, text="hi"
        )
        assert created is True
        conv.refresh_from_db()
        assert conv.last_message_id == message.id
        assert conv.updated_at == message.created_at
        # unread инкрементится только получателю
        assert _unread(conv, b) == 1
        assert _unread(conv, a) == 0

    def test_idempotent_retry_same_id(self) -> None:
        a, b = _pair()
        conv = _conversation(a, b)
        mid = uuid4()
        ChatService.send_message(
            sender=a, conversation_id=conv.id, client_message_id=mid, text="hi"
        )
        _message, created = ChatService.send_message(
            sender=a, conversation_id=conv.id, client_message_id=mid, text="hi"
        )
        assert created is False
        assert Message.objects.count() == 1
        assert _unread(conv, b) == 1  # не задвоилось

    def test_id_reuse_other_conversation_conflicts(self) -> None:
        a, b = _pair()
        c = onboarded_user(display_name="c")
        make_friends(a, c)
        conv_ab = _conversation(a, b)
        conv_ac = _conversation(a, c)
        mid = uuid4()
        ChatService.send_message(
            sender=a, conversation_id=conv_ab.id, client_message_id=mid, text="hi"
        )
        with pytest.raises(MessageConflict):
            ChatService.send_message(
                sender=a, conversation_id=conv_ac.id, client_message_id=mid, text="hi"
            )

    def test_empty_text_rejected(self) -> None:
        a, b = _pair()
        conv = _conversation(a, b)
        with pytest.raises(EmptyMessage):
            ChatService.send_message(
                sender=a, conversation_id=conv.id, client_message_id=uuid4(), text="   "
            )

    def test_too_long_rejected(self) -> None:
        a, b = _pair()
        conv = _conversation(a, b)
        with pytest.raises(MessageTooLong):
            ChatService.send_message(
                sender=a,
                conversation_id=conv.id,
                client_message_id=uuid4(),
                text="x" * 4001,
            )

    def test_non_participant_rejected(self) -> None:
        a, b = _pair()
        conv = _conversation(a, b)
        outsider = onboarded_user(display_name="out")
        with pytest.raises(ConversationNotFound):
            ChatService.send_message(
                sender=outsider,
                conversation_id=conv.id,
                client_message_id=uuid4(),
                text="hi",
            )


@pytest.mark.django_db
class TestMarkRead:
    def test_marks_incoming_and_resets_unread(self) -> None:
        a, b = _pair()
        conv = _conversation(a, b)
        ChatService.send_message(
            sender=a, conversation_id=conv.id, client_message_id=uuid4(), text="1"
        )
        ChatService.send_message(
            sender=a, conversation_id=conv.id, client_message_id=uuid4(), text="2"
        )
        read_ids, peer_id = ChatService.mark_read(user=b, conversation_id=conv.id)
        assert len(read_ids) == 2
        assert peer_id == a.pk
        assert _unread(conv, b) == 0
        assert Message.objects.filter(read_at__isnull=False).count() == 2

    def test_excludes_own_messages(self) -> None:
        a, b = _pair()
        conv = _conversation(a, b)
        # b отправляет — это исходящее для b, в его read-receipt не попадает
        ChatService.send_message(
            sender=b, conversation_id=conv.id, client_message_id=uuid4(), text="mine"
        )
        read_ids, _ = ChatService.mark_read(user=b, conversation_id=conv.id)
        assert read_ids == []


@pytest.mark.django_db
class TestMarkPendingDelivered:
    def test_delivers_incoming_offline(self) -> None:
        a, b = _pair()
        conv = _conversation(a, b)
        ChatService.send_message(
            sender=a, conversation_id=conv.id, client_message_id=uuid4(), text="hi"
        )
        rows = ChatService.mark_pending_delivered(user=b)
        assert len(rows) == 1
        _, author_id, conversation_id = rows[0]
        assert author_id == a.pk
        assert conversation_id == conv.id
        assert Message.objects.filter(delivered_at__isnull=False).count() == 1
        # повторно — уже доставлено, пусто
        assert ChatService.mark_pending_delivered(user=b) == []


def _unread(conv, user):  # type: ignore[no-untyped-def]
    return ConversationParticipant.objects.get(conversation=conv, user=user).unread_count
