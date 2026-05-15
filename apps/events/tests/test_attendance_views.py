"""HTTP-тесты attendance-эндпоинтов."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APIClient

from apps.events.tests.factories import EventFactory
from apps.social.models import FriendshipStatus
from apps.social.tests.factories import FriendshipFactory
from apps.users.tests.factories import UserFactory


def _attendance_url(event_id: int) -> str:
    return reverse("events:attendance", kwargs={"event_id": event_id})


def _onboarded_user(**kwargs):
    """Юзер, прошедший все permission-чекмарки."""
    defaults = {
        "email_verified_at": now(),
        "display_name": kwargs.pop("display_name", "u"),
        "consent_at": now(),
    }
    defaults.update(kwargs)
    return UserFactory(**defaults)


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestAttendanceAuth:
    def test_anonymous_blocked(self, api: APIClient) -> None:
        event = EventFactory()
        resp = api.post(_attendance_url(event.pk))
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unverified_blocked(self, api: APIClient) -> None:
        user = UserFactory(email_verified_at=None, display_name="x", consent_at=now())
        api.force_authenticate(user)
        event = EventFactory()
        resp = api.post(_attendance_url(event.pk))
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_not_onboarded_blocked(self, api: APIClient) -> None:
        user = UserFactory(email_verified_at=now(), display_name="", consent_at=None)
        api.force_authenticate(user)
        event = EventFactory()
        resp = api.post(_attendance_url(event.pk))
        assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestAttendanceFlow:
    def test_post_marks_going(self, api: APIClient) -> None:
        user = _onboarded_user()
        api.force_authenticate(user)
        event = EventFactory()

        resp = api.post(_attendance_url(event.pk))
        assert resp.status_code == 200
        assert resp.data["is_going"] is True
        assert resp.data["attendees_count"] == 1
        assert resp.data["friends_attending"] == []

    def test_post_is_idempotent(self, api: APIClient) -> None:
        user = _onboarded_user()
        api.force_authenticate(user)
        event = EventFactory()

        api.post(_attendance_url(event.pk))
        resp = api.post(_attendance_url(event.pk))
        assert resp.status_code == 200
        assert resp.data["attendees_count"] == 1

    def test_delete_cancels(self, api: APIClient) -> None:
        user = _onboarded_user()
        api.force_authenticate(user)
        event = EventFactory()

        api.post(_attendance_url(event.pk))
        resp = api.delete(_attendance_url(event.pk))
        assert resp.status_code == 200
        assert resp.data["is_going"] is False
        assert resp.data["attendees_count"] == 0

    def test_get_returns_state(self, api: APIClient) -> None:
        user = _onboarded_user()
        api.force_authenticate(user)
        event = EventFactory()

        resp = api.get(_attendance_url(event.pk))
        assert resp.status_code == 200
        assert resp.data == {
            "is_going": False,
            "attendees_count": 0,
            "friends_attending": [],
        }

    def test_event_not_found(self, api: APIClient) -> None:
        user = _onboarded_user()
        api.force_authenticate(user)

        resp = api.post(_attendance_url(999_999))
        assert resp.status_code == 404
        assert resp.data["code"] == "event_not_found"


@pytest.mark.django_db
class TestFriendsAttending:
    def test_shows_only_friends_not_strangers(self, api: APIClient) -> None:
        viewer = _onboarded_user()
        friend = _onboarded_user()
        stranger = _onboarded_user()
        FriendshipFactory(
            from_user=viewer, to_user=friend,
            status=FriendshipStatus.ACCEPTED,
        )
        event = EventFactory()

        # Друг и незнакомец оба идут
        api.force_authenticate(friend)
        api.post(_attendance_url(event.pk))
        api.force_authenticate(stranger)
        api.post(_attendance_url(event.pk))

        api.force_authenticate(viewer)
        resp = api.get(_attendance_url(event.pk))

        assert resp.data["attendees_count"] == 2
        friends = resp.data["friends_attending"]
        assert len(friends) == 1
        assert friends[0]["user"]["id"] == friend.pk

    def test_friendship_both_directions(self, api: APIClient) -> None:
        """Дружба засчитывается в любом направлении."""
        viewer = _onboarded_user()
        friend = _onboarded_user()
        # Заявка пришла другу, не от нас
        FriendshipFactory(
            from_user=friend, to_user=viewer,
            status=FriendshipStatus.ACCEPTED,
        )
        event = EventFactory()

        api.force_authenticate(friend)
        api.post(_attendance_url(event.pk))

        api.force_authenticate(viewer)
        resp = api.get(_attendance_url(event.pk))
        assert len(resp.data["friends_attending"]) == 1

    def test_pending_friendship_not_counted(self, api: APIClient) -> None:
        viewer = _onboarded_user()
        not_yet_friend = _onboarded_user()
        FriendshipFactory(
            from_user=viewer, to_user=not_yet_friend,
            status=FriendshipStatus.PENDING,
        )
        event = EventFactory()

        api.force_authenticate(not_yet_friend)
        api.post(_attendance_url(event.pk))

        api.force_authenticate(viewer)
        resp = api.get(_attendance_url(event.pk))
        assert len(resp.data["friends_attending"]) == 0


@pytest.mark.django_db
class TestEventDetailIncludesAttendance:
    """GET /api/events/{id} должен содержать attendance-поля."""

    def test_anonymous_sees_count_but_not_friends(self, api: APIClient) -> None:
        event = EventFactory()
        AttendanceService_user = _onboarded_user()
        api.force_authenticate(AttendanceService_user)
        api.post(_attendance_url(event.pk))

        api.logout()
        api.force_authenticate(user=None)
        resp = api.get(reverse("events:detail", kwargs={"pk": event.pk}))
        assert resp.status_code == 200
        assert resp.data["attendees_count"] == 1
        assert resp.data["is_going"] is False
        assert resp.data["friends_attending"] == []

    def test_authenticated_sees_full_state(self, api: APIClient) -> None:
        viewer = _onboarded_user()
        friend = _onboarded_user()
        FriendshipFactory(
            from_user=viewer, to_user=friend,
            status=FriendshipStatus.ACCEPTED,
        )
        event = EventFactory()

        api.force_authenticate(friend)
        api.post(_attendance_url(event.pk))
        api.force_authenticate(viewer)
        api.post(_attendance_url(event.pk))

        resp = api.get(reverse("events:detail", kwargs={"pk": event.pk}))
        assert resp.data["attendees_count"] == 2
        assert resp.data["is_going"] is True
        assert len(resp.data["friends_attending"]) == 1