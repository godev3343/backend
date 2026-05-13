"""Тесты HTTP-эндпоинтов friend requests / friends."""

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APIClient

from apps.social.models import Friendship, FriendshipStatus
from apps.social.tests.factories import FriendshipFactory
from apps.users.tests.factories import UserFactory


def _onboarded_user(**kwargs):  # type: ignore[no-untyped-def]
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
class TestSendRequest:
    def test_send_request_creates(self, client: APIClient) -> None:
        a = _onboarded_user(display_name="a")
        b = _onboarded_user(display_name="b")
        client.force_authenticate(a)
        resp = client.post(
            reverse("social:friend_request_create"),
            {"to_user_id": b.pk},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["status"] == FriendshipStatus.PENDING

    def test_send_self_400(self, client: APIClient) -> None:
        a = _onboarded_user()
        client.force_authenticate(a)
        resp = client.post(
            reverse("social:friend_request_create"),
            {"to_user_id": a.pk},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["code"] == "self_friendship"

    def test_send_duplicate_409(self, client: APIClient) -> None:
        a, b = _onboarded_user(display_name="a"), _onboarded_user(display_name="b")
        client.force_authenticate(a)
        client.post(
            reverse("social:friend_request_create"),
            {"to_user_id": b.pk},
            format="json",
        )
        resp = client.post(
            reverse("social:friend_request_create"),
            {"to_user_id": b.pk},
            format="json",
        )
        assert resp.status_code == status.HTTP_409_CONFLICT
        assert resp.json()["code"] == "friendship_exists"

    def test_send_to_unknown_404(self, client: APIClient) -> None:
        a = _onboarded_user()
        client.force_authenticate(a)
        resp = client.post(
            reverse("social:friend_request_create"),
            {"to_user_id": 999_999},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_send_unverified_email_forbidden(self, client: APIClient) -> None:
        a = UserFactory(email_verified_at=None, consent_at=now(), display_name="x")
        b = _onboarded_user()
        client.force_authenticate(a)
        resp = client.post(
            reverse("social:friend_request_create"),
            {"to_user_id": b.pk},
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_send_counter_pending_auto_accepts(self, client: APIClient) -> None:
        a, b = _onboarded_user(display_name="a"), _onboarded_user(display_name="b")
        # b → a уже отправил
        FriendshipFactory(from_user=b, to_user=a)
        client.force_authenticate(a)
        resp = client.post(
            reverse("social:friend_request_create"),
            {"to_user_id": b.pk},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.json()["status"] == FriendshipStatus.ACCEPTED
        assert Friendship.objects.count() == 1


@pytest.mark.django_db
class TestAcceptDecline:
    def test_accept_changes_status(self, client: APIClient) -> None:
        a, b = _onboarded_user(display_name="a"), _onboarded_user(display_name="b")
        f = FriendshipFactory(from_user=a, to_user=b)
        client.force_authenticate(b)
        resp = client.post(reverse("social:friend_request_accept", args=[f.pk]))
        assert resp.status_code == status.HTTP_200_OK
        f.refresh_from_db()
        assert f.status == FriendshipStatus.ACCEPTED

    def test_accept_by_sender_forbidden(self, client: APIClient) -> None:
        a, b = _onboarded_user(display_name="a"), _onboarded_user(display_name="b")
        f = FriendshipFactory(from_user=a, to_user=b)
        client.force_authenticate(a)
        resp = client.post(reverse("social:friend_request_accept", args=[f.pk]))
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.json()["code"] == "not_recipient"

    def test_decline_hard_deletes(self, client: APIClient) -> None:
        a, b = _onboarded_user(display_name="a"), _onboarded_user(display_name="b")
        f = FriendshipFactory(from_user=a, to_user=b)
        client.force_authenticate(b)
        resp = client.post(reverse("social:friend_request_decline", args=[f.pk]))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not Friendship.objects.filter(pk=f.pk).exists()

    def test_decline_then_resend(self, client: APIClient) -> None:
        a, b = _onboarded_user(display_name="a"), _onboarded_user(display_name="b")
        f = FriendshipFactory(from_user=a, to_user=b)
        client.force_authenticate(b)
        client.post(reverse("social:friend_request_decline", args=[f.pk]))
        # a снова шлёт b
        client.force_authenticate(a)
        resp = client.post(
            reverse("social:friend_request_create"),
            {"to_user_id": b.pk},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestCancelRequest:
    def test_cancel_outgoing(self, client: APIClient) -> None:
        a, b = _onboarded_user(display_name="a"), _onboarded_user(display_name="b")
        f = FriendshipFactory(from_user=a, to_user=b)
        client.force_authenticate(a)
        resp = client.delete(reverse("social:friend_request_cancel", args=[f.pk]))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not Friendship.objects.filter(pk=f.pk).exists()

    def test_cancel_by_recipient_forbidden(self, client: APIClient) -> None:
        a, b = _onboarded_user(display_name="a"), _onboarded_user(display_name="b")
        f = FriendshipFactory(from_user=a, to_user=b)
        client.force_authenticate(b)
        resp = client.delete(reverse("social:friend_request_cancel", args=[f.pk]))
        assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestRequestLists:
    def test_incoming(self, client: APIClient) -> None:
        a, b, c = (
            _onboarded_user(display_name="a"),
            _onboarded_user(display_name="b"),
            _onboarded_user(display_name="c"),
        )
        f1 = FriendshipFactory(from_user=b, to_user=a)
        FriendshipFactory(from_user=c, to_user=a)
        # accepted не должен попасть
        d = _onboarded_user(display_name="d")
        FriendshipFactory(from_user=d, to_user=a, status=FriendshipStatus.ACCEPTED)
        client.force_authenticate(a)
        resp = client.get(reverse("social:friend_requests_incoming"))
        ids = [r["id"] for r in resp.json()["results"]]
        assert len(ids) == 2
        assert f1.pk in ids

    def test_outgoing(self, client: APIClient) -> None:
        a, b = _onboarded_user(display_name="a"), _onboarded_user(display_name="b")
        f = FriendshipFactory(from_user=a, to_user=b)
        client.force_authenticate(a)
        resp = client.get(reverse("social:friend_requests_outgoing"))
        ids = [r["id"] for r in resp.json()["results"]]
        assert ids == [f.pk]


@pytest.mark.django_db
class TestFriendList:
    def test_lists_both_directions(self, client: APIClient) -> None:
        a = _onboarded_user(display_name="a")
        b = _onboarded_user(display_name="b")
        c = _onboarded_user(display_name="c")
        FriendshipFactory(from_user=a, to_user=b, status=FriendshipStatus.ACCEPTED)
        FriendshipFactory(from_user=c, to_user=a, status=FriendshipStatus.ACCEPTED)
        client.force_authenticate(a)
        resp = client.get(reverse("social:friend_list"))
        ids = {r["id"] for r in resp.json()["results"]}
        assert ids == {b.pk, c.pk}

    def test_remove_friend(self, client: APIClient) -> None:
        a = _onboarded_user(display_name="a")
        b = _onboarded_user(display_name="b")
        FriendshipFactory(from_user=a, to_user=b, status=FriendshipStatus.ACCEPTED)
        client.force_authenticate(a)
        resp = client.delete(reverse("social:friend_remove", args=[b.pk]))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not Friendship.objects.exists()

    def test_remove_when_not_friends_404(self, client: APIClient) -> None:
        a = _onboarded_user(display_name="a")
        b = _onboarded_user(display_name="b")
        client.force_authenticate(a)
        resp = client.delete(reverse("social:friend_remove", args=[b.pk]))
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestE2EFlow:
    """Happy-path: send → accept → list → remove."""

    def test_full_flow(self, client: APIClient) -> None:
        a = _onboarded_user(display_name="a")
        b = _onboarded_user(display_name="b")

        # 1. a отправляет заявку b
        client.force_authenticate(a)
        resp = client.post(
            reverse("social:friend_request_create"),
            {"to_user_id": b.pk},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        friendship_id = resp.json()["id"]

        # 2. b видит входящую
        client.force_authenticate(b)
        resp = client.get(reverse("social:friend_requests_incoming"))
        assert resp.json()["count"] == 1

        # 3. b принимает
        resp = client.post(reverse("social:friend_request_accept", args=[friendship_id]))
        assert resp.status_code == status.HTTP_200_OK

        # 4. Оба видят друг друга в /friends
        for u in (a, b):
            client.force_authenticate(u)
            resp = client.get(reverse("social:friend_list"))
            assert resp.json()["count"] == 1

        # 5. a удаляет b
        client.force_authenticate(a)
        resp = client.delete(reverse("social:friend_remove", args=[b.pk]))
        assert resp.status_code == status.HTTP_204_NO_CONTENT

        # 6. У обоих пусто
        for u in (a, b):
            client.force_authenticate(u)
            resp = client.get(reverse("social:friend_list"))
            assert resp.json()["count"] == 0
