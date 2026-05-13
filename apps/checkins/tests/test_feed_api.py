# apps/checkins/tests/test_feed_api.py
"""Тесты GET /api/feed."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.checkins.tests.factories import CheckInFactory
from apps.social.models import FriendshipStatus
from apps.social.tests.factories import FriendshipFactory
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestFeedAPI:
    def test_returns_friends_checkins(self, authed_client, user) -> None:  # type: ignore[no-untyped-def]
        friend = UserFactory()
        FriendshipFactory(from_user=user, to_user=friend, status=FriendshipStatus.ACCEPTED)
        friend_checkin = CheckInFactory(user=friend)

        url = reverse("checkins:feed")
        resp = authed_client.get(url)
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.data["results"]]
        assert friend_checkin.pk in ids

    def test_excludes_strangers(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        stranger = UserFactory()
        CheckInFactory(user=stranger)
        url = reverse("checkins:feed")
        resp = authed_client.get(url)
        assert resp.data["results"] == []

    def test_excludes_self(self, authed_client, user) -> None:  # type: ignore[no-untyped-def]
        """/api/feed — это лента ДРУЗЕЙ. Свои чек-ины через /me."""
        CheckInFactory(user=user)
        url = reverse("checkins:feed")
        resp = authed_client.get(url)
        assert resp.data["results"] == []

    def test_pending_friendship_does_not_count(self, authed_client, user) -> None:  # type: ignore[no-untyped-def]
        """Только accepted друзья. Pending — мимо."""
        target = UserFactory()
        FriendshipFactory(from_user=user, to_user=target, status=FriendshipStatus.PENDING)
        CheckInFactory(user=target)
        url = reverse("checkins:feed")
        resp = authed_client.get(url)
        assert resp.data["results"] == []

    def test_reverse_friendship_direction_counts(self, authed_client, user) -> None:  # type: ignore[no-untyped-def]
        """Дружба учитывается в любом направлении (from→to и to→from)."""
        friend = UserFactory()
        # Заявка ОТ friend К user (reverse direction)
        FriendshipFactory(from_user=friend, to_user=user, status=FriendshipStatus.ACCEPTED)
        checkin = CheckInFactory(user=friend)
        url = reverse("checkins:feed")
        resp = authed_client.get(url)
        ids = [item["id"] for item in resp.data["results"]]
        assert checkin.pk in ids

    def test_ordering_newest_first(self, authed_client, user) -> None:  # type: ignore[no-untyped-def]
        friend = UserFactory()
        FriendshipFactory(from_user=user, to_user=friend, status=FriendshipStatus.ACCEPTED)
        c1 = CheckInFactory(user=friend)
        c2 = CheckInFactory(user=friend)  # позже по created_at
        url = reverse("checkins:feed")
        resp = authed_client.get(url)
        ids = [item["id"] for item in resp.data["results"]]
        # c2 (новее) первый
        assert ids == [c2.pk, c1.pk]

    def test_is_liked_in_response(self, authed_client, user) -> None:  # type: ignore[no-untyped-def]
        """is_liked в фиде должен быть bool, не null."""
        from apps.checkins.services import LikeService

        friend = UserFactory()
        FriendshipFactory(from_user=user, to_user=friend, status=FriendshipStatus.ACCEPTED)
        checkin = CheckInFactory(user=friend)
        LikeService.like(user=user, checkin_id=checkin.pk)

        url = reverse("checkins:feed")
        resp = authed_client.get(url)
        item = resp.data["results"][0]
        assert item["is_liked"] is True
        assert item["likes_count"] == 1

    def test_unauthenticated_401(self, api_client) -> None:  # type: ignore[no-untyped-def]
        url = reverse("checkins:feed")
        resp = api_client.get(url)
        assert resp.status_code == 401
