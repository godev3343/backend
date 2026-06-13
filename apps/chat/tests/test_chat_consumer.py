"""
WebSocket-тесты ChatConsumer (Channels, InMemoryChannelLayer).

Гоняем полный стек middleware → consumer через WebsocketCommunicator.
transaction=True — потому что consumer лезет в БД из отдельного потока
(database_sync_to_async): данные теста должны быть закоммичены и видны там.
presence мокаем (Redis в тестах может быть недоступен; presence best-effort).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from channels.db import database_sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.tokens import AccessToken

from apps.chat.middleware import JWTAuthMiddleware
from apps.chat.routing import websocket_urlpatterns
from apps.chat.services import ChatService
from apps.chat.tests.factories import make_friends, onboarded_user

pytestmark = pytest.mark.django_db(transaction=True)

_RECV_TIMEOUT = 5


@pytest.fixture(autouse=True)
def _mock_presence(mocker):  # type: ignore[no-untyped-def]
    """presence не зависит от Redis: оба участника считаются онлайн."""
    mocker.patch("apps.chat.services.presence.PresenceService.connected", return_value=None)
    mocker.patch("apps.chat.services.presence.PresenceService.disconnected", return_value=None)
    mocker.patch("apps.chat.services.presence.PresenceService.is_online", return_value=True)


def _application():  # type: ignore[no-untyped-def]
    return JWTAuthMiddleware(URLRouter(websocket_urlpatterns))


@database_sync_to_async
def _setup_pair():  # type: ignore[no-untyped-def]
    a = onboarded_user(display_name="Alice")
    b = onboarded_user(display_name="Bob")
    make_friends(a, b)
    conv, _ = ChatService.get_or_create_conversation(user=a, peer_id=b.pk)
    return a, b, conv


@database_sync_to_async
def _token(user):  # type: ignore[no-untyped-def]
    return str(AccessToken.for_user(user))


async def _connect(user):  # type: ignore[no-untyped-def]
    token = await _token(user)
    communicator = WebsocketCommunicator(_application(), f"/ws/chat?token={token}")
    connected, _ = await communicator.connect()
    return communicator, connected


async def test_unauthenticated_rejected():  # type: ignore[no-untyped-def]
    communicator = WebsocketCommunicator(_application(), "/ws/chat")
    connected, _ = await communicator.connect()
    assert connected is False
    await communicator.disconnect()


async def test_send_message_flow():  # type: ignore[no-untyped-def]
    a, b, conv = await _setup_pair()
    comm_a, ok_a = await _connect(a)
    comm_b, ok_b = await _connect(b)
    assert ok_a and ok_b

    mid = str(uuid4())
    await comm_a.send_json_to(
        {
            "type": "message.send",
            "client_message_id": mid,
            "conversation_id": str(conv.id),
            "text": "привет",
        }
    )

    # Отправитель: sent → delivered (получатель онлайн).
    sent = await comm_a.receive_json_from(timeout=_RECV_TIMEOUT)
    assert sent == {
        "type": "message.status",
        "conversation_id": str(conv.id),
        "message_id": mid,
        "status": "sent",
    }
    delivered = await comm_a.receive_json_from(timeout=_RECV_TIMEOUT)
    assert delivered["status"] == "delivered"
    assert delivered["message_id"] == mid

    # Получатель: message.received с полным сообщением.
    received = await comm_b.receive_json_from(timeout=_RECV_TIMEOUT)
    assert received["type"] == "message.received"
    assert received["message"]["id"] == mid
    assert received["message"]["text"] == "привет"
    assert received["message"]["sender_id"] == a.pk
    assert received["message"]["conversation_id"] == str(conv.id)

    await comm_a.disconnect()
    await comm_b.disconnect()


async def test_read_notifies_author():  # type: ignore[no-untyped-def]
    a, b, conv = await _setup_pair()
    comm_a, _ = await _connect(a)
    comm_b, _ = await _connect(b)

    mid = str(uuid4())
    await comm_a.send_json_to(
        {
            "type": "message.send",
            "client_message_id": mid,
            "conversation_id": str(conv.id),
            "text": "ok?",
        }
    )
    # Сливаем sent+delivered у автора и received у получателя.
    await comm_a.receive_json_from(timeout=_RECV_TIMEOUT)  # sent
    await comm_a.receive_json_from(timeout=_RECV_TIMEOUT)  # delivered
    await comm_b.receive_json_from(timeout=_RECV_TIMEOUT)  # received

    await comm_b.send_json_to(
        {"type": "message.read", "conversation_id": str(conv.id), "message_id": mid}
    )
    read = await comm_a.receive_json_from(timeout=_RECV_TIMEOUT)
    assert read["type"] == "message.status"
    assert read["status"] == "read"
    assert read["message_id"] == mid

    await comm_a.disconnect()
    await comm_b.disconnect()


async def test_typing_relayed_to_peer():  # type: ignore[no-untyped-def]
    a, b, conv = await _setup_pair()
    comm_a, _ = await _connect(a)
    comm_b, _ = await _connect(b)

    await comm_b.send_json_to(
        {"type": "typing", "conversation_id": str(conv.id), "is_typing": True}
    )
    event = await comm_a.receive_json_from(timeout=_RECV_TIMEOUT)
    assert event == {
        "type": "typing",
        "conversation_id": str(conv.id),
        "is_typing": True,
    }

    await comm_a.disconnect()
    await comm_b.disconnect()
