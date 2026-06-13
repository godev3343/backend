"""HTTP-тесты chat REST-эндпоинтов."""

from __future__ import annotations

from uuid import uuid4

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.chat.services import ChatService
from apps.chat.tests.factories import make_friends, onboarded_user


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _pair():  # type: ignore[no-untyped-def]
    a = onboarded_user(display_name="Alice")
    b = onboarded_user(display_name="Bob")
    make_friends(a, b)
    return a, b


@pytest.mark.django_db
class TestCreateConversation:
    def test_create_then_idempotent(self, client: APIClient) -> None:
        a, b = _pair()
        client.force_authenticate(a)
        url = reverse("chat:conversation_list")

        resp = client.post(url, {"user_id": b.pk}, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        body = resp.json()
        assert body["peer"]["id"] == b.pk
        assert body["peer"]["display_name"] == "Bob"
        assert body["unread_count"] == 0

        # повторно — та же переписка, 200
        resp2 = client.post(url, {"user_id": b.pk}, format="json")
        assert resp2.status_code == status.HTTP_200_OK
        assert resp2.json()["id"] == body["id"]

    def test_create_with_non_friend_forbidden(self, client: APIClient) -> None:
        a = onboarded_user(display_name="a")
        b = onboarded_user(display_name="b")  # не друг
        client.force_authenticate(a)
        resp = client.post(reverse("chat:conversation_list"), {"user_id": b.pk}, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.json()["code"] == "not_friends"

    def test_create_with_self_400(self, client: APIClient) -> None:
        a = onboarded_user()
        client.force_authenticate(a)
        resp = client.post(reverse("chat:conversation_list"), {"user_id": a.pk}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["code"] == "self_conversation"

    def test_create_unknown_user_404(self, client: APIClient) -> None:
        a = onboarded_user()
        client.force_authenticate(a)
        resp = client.post(reverse("chat:conversation_list"), {"user_id": 999_999}, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_requires_auth(self, client: APIClient) -> None:
        resp = client.post(reverse("chat:conversation_list"), {"user_id": 1}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestListConversations:
    def test_empty(self, client: APIClient) -> None:
        a = onboarded_user()
        client.force_authenticate(a)
        resp = client.get(reverse("chat:conversation_list"))
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["results"] == []

    def test_lists_with_unread_and_last_message(self, client: APIClient) -> None:
        a, b = _pair()
        conv, _ = ChatService.get_or_create_conversation(user=a, peer_id=b.pk)
        ChatService.send_message(
            sender=b, conversation_id=conv.id, client_message_id=uuid4(), text="hello a"
        )
        client.force_authenticate(a)
        resp = client.get(reverse("chat:conversation_list"))
        assert resp.status_code == status.HTTP_200_OK
        results = resp.json()["results"]
        assert len(results) == 1
        item = results[0]
        assert item["id"] == str(conv.id)
        assert item["peer"]["id"] == b.pk
        assert item["unread_count"] == 1
        assert item["last_message"]["text"] == "hello a"
        assert item["last_message"]["sender_id"] == b.pk

    def test_sorted_by_updated_desc(self, client: APIClient) -> None:
        a, b = _pair()
        c = onboarded_user(display_name="Carol")
        make_friends(a, c)
        conv_ab, _ = ChatService.get_or_create_conversation(user=a, peer_id=b.pk)
        conv_ac, _ = ChatService.get_or_create_conversation(user=a, peer_id=c.pk)
        # пишем в ab позже — он должен быть выше
        ChatService.send_message(
            sender=a, conversation_id=conv_ac.id, client_message_id=uuid4(), text="ac"
        )
        ChatService.send_message(
            sender=a, conversation_id=conv_ab.id, client_message_id=uuid4(), text="ab"
        )
        client.force_authenticate(a)
        resp = client.get(reverse("chat:conversation_list"))
        ids = [r["id"] for r in resp.json()["results"]]
        assert ids == [str(conv_ab.id), str(conv_ac.id)]


@pytest.mark.django_db
class TestMessageHistory:
    def test_returns_messages_newest_first(self, client: APIClient) -> None:
        a, b = _pair()
        conv, _ = ChatService.get_or_create_conversation(user=a, peer_id=b.pk)
        ChatService.send_message(
            sender=a, conversation_id=conv.id, client_message_id=uuid4(), text="first"
        )
        ChatService.send_message(
            sender=b, conversation_id=conv.id, client_message_id=uuid4(), text="second"
        )
        client.force_authenticate(a)
        url = reverse("chat:conversation_messages", kwargs={"conversation_id": conv.id})
        resp = client.get(url)
        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert body["count"] == 2
        texts = [m["text"] for m in body["results"]]
        assert texts == ["second", "first"]  # desc

    def test_non_participant_404(self, client: APIClient) -> None:
        a, b = _pair()
        conv, _ = ChatService.get_or_create_conversation(user=a, peer_id=b.pk)
        outsider = onboarded_user(display_name="out")
        client.force_authenticate(outsider)
        url = reverse("chat:conversation_messages", kwargs={"conversation_id": conv.id})
        resp = client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_unknown_conversation_404(self, client: APIClient) -> None:
        a = onboarded_user()
        client.force_authenticate(a)
        url = reverse("chat:conversation_messages", kwargs={"conversation_id": uuid4()})
        resp = client.get(url)
        assert resp.status_code == status.HTTP_404_NOT_FOUND
