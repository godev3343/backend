# apps/social/tests/test_user_search.py
"""
Интеграционные тесты GET /api/users/search.

Главная цель — убедиться что выдача поиска содержит friendship_id для
pending-заявок (бэк-долг #5). Без этого фронт-кнопки «Отменить» /
«Принять» работают только когда юзер пришёл из /friends (через кеш).

Onboarded-юзер обязателен — UserSearchView требует IsOnboarded permission.
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APIClient

from apps.social.models import Friendship, FriendshipStatus
from apps.users.tests.factories import UserFactory


def _onboarded_user(**kwargs):  # type: ignore[no-untyped-def]
    """Юзер с display_name + consent_at, проходит IsOnboarded."""
    defaults = {
        "email_verified_at": now(),
        "consent_at": now(),
        "display_name": kwargs.pop("display_name", None) or "user",
    }
    defaults.update(kwargs)
    return UserFactory(**defaults)


@pytest.fixture
def client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestUserSearchFriendshipId:
    """friendship_id присутствует в payload для каждой релевантной связи."""

    def test_pending_outgoing_returns_friendship_id(self, client: APIClient) -> None:
        viewer = _onboarded_user(display_name="viewer")
        target = _onboarded_user(display_name="Aidar Search Target")
        f = Friendship.objects.create(
            from_user=viewer,
            to_user=target,
            status=FriendshipStatus.PENDING,
        )
        client.force_authenticate(viewer)

        resp = client.get(reverse("social:user_search"), {"q": "Aidar"})

        assert resp.status_code == status.HTTP_200_OK
        results = resp.json()["results"]
        row = next(r for r in results if r["id"] == target.pk)
        assert row["friendship_status"] == "pending_outgoing"
        assert row["friendship_id"] == f.pk

    def test_pending_incoming_returns_friendship_id(self, client: APIClient) -> None:
        viewer = _onboarded_user(display_name="viewer")
        target = _onboarded_user(display_name="Borya Inbound")
        f = Friendship.objects.create(
            from_user=target,
            to_user=viewer,
            status=FriendshipStatus.PENDING,
        )
        client.force_authenticate(viewer)

        resp = client.get(reverse("social:user_search"), {"q": "Borya"})

        assert resp.status_code == status.HTTP_200_OK
        results = resp.json()["results"]
        row = next(r for r in results if r["id"] == target.pk)
        assert row["friendship_status"] == "pending_incoming"
        assert row["friendship_id"] == f.pk

    def test_friends_returns_null_friendship_id(self, client: APIClient) -> None:
        """Для друзей кнопка accept/decline не нужна → id null."""
        viewer = _onboarded_user(display_name="viewer")
        target = _onboarded_user(display_name="Chingiz Friend")
        Friendship.objects.create(
            from_user=viewer,
            to_user=target,
            status=FriendshipStatus.ACCEPTED,
        )
        client.force_authenticate(viewer)

        resp = client.get(reverse("social:user_search"), {"q": "Chingiz"})

        assert resp.status_code == status.HTTP_200_OK
        results = resp.json()["results"]
        row = next(r for r in results if r["id"] == target.pk)
        assert row["friendship_status"] == "friends"
        assert row["friendship_id"] is None

    def test_no_relation_returns_null_friendship_id(self, client: APIClient) -> None:
        """Незнакомый юзер — кнопка add → id не нужен."""
        viewer = _onboarded_user(display_name="viewer")
        target = _onboarded_user(display_name="Dauren Stranger")
        client.force_authenticate(viewer)

        resp = client.get(reverse("social:user_search"), {"q": "Dauren"})

        assert resp.status_code == status.HTTP_200_OK
        results = resp.json()["results"]
        row = next(r for r in results if r["id"] == target.pk)
        assert row["friendship_status"] == "none"
        assert row["friendship_id"] is None

    def test_payload_contains_friendship_id_field(self, client: APIClient) -> None:
        """
        Контрактный тест: поле friendship_id всегда присутствует в каждом
        элементе выдачи, даже когда оно null. Защищает от регрессии в
        сериализаторе (поле случайно удалили / поставили required=False).
        """
        viewer = _onboarded_user(display_name="viewer")
        _onboarded_user(display_name="Erlan Contract")
        client.force_authenticate(viewer)

        resp = client.get(reverse("social:user_search"), {"q": "Erlan"})

        assert resp.status_code == status.HTTP_200_OK
        results = resp.json()["results"]
        assert len(results) >= 1
        for row in results:
            assert "friendship_id" in row
            assert "friendship_status" in row