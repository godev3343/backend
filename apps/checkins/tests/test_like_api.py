# apps/checkins/tests/test_like_api.py
"""Тесты POST/DELETE /api/checkins/{id}/like."""

from __future__ import annotations

import pytest
from django.urls import reverse

from apps.checkins.tests.factories import CheckInFactory


@pytest.mark.django_db
class TestLikeAPI:
    def test_first_like_201(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        checkin = CheckInFactory()
        url = reverse("checkins:like", kwargs={"pk": checkin.pk})
        resp = authed_client.post(url)
        assert resp.status_code == 201
        assert resp.data["is_liked"] is True
        assert resp.data["likes_count"] == 1

    def test_repeat_like_200_idempotent(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        checkin = CheckInFactory()
        url = reverse("checkins:like", kwargs={"pk": checkin.pk})
        authed_client.post(url)
        resp = authed_client.post(url)
        assert resp.status_code == 200
        assert resp.data["likes_count"] == 1  # без накрутки

    def test_unlike_200(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        checkin = CheckInFactory()
        url = reverse("checkins:like", kwargs={"pk": checkin.pk})
        authed_client.post(url)

        resp = authed_client.delete(url)
        assert resp.status_code == 200
        assert resp.data["is_liked"] is False
        assert resp.data["likes_count"] == 0

    def test_unlike_when_no_like_idempotent(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        checkin = CheckInFactory()
        url = reverse("checkins:like", kwargs={"pk": checkin.pk})
        resp = authed_client.delete(url)
        assert resp.status_code == 200
        assert resp.data["likes_count"] == 0

    def test_checkin_not_found_404(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        url = reverse("checkins:like", kwargs={"pk": 999_999})
        resp = authed_client.post(url)
        assert resp.status_code == 404
        assert resp.data["code"] == "checkin_not_found"

    def test_unauthenticated_401(self, api_client) -> None:  # type: ignore[no-untyped-def]
        checkin = CheckInFactory()
        url = reverse("checkins:like", kwargs={"pk": checkin.pk})
        resp = api_client.post(url)
        assert resp.status_code == 401

    def test_two_users_independent_likes(  # type: ignore[no-untyped-def]
        self, authed_client, another_authed_client
    ) -> None:
        checkin = CheckInFactory()
        url = reverse("checkins:like", kwargs={"pk": checkin.pk})

        authed_client.post(url)
        another_authed_client.post(url)

        resp = authed_client.delete(url)
        # У authed_client лайка нет, но у another_user остался → likes_count = 1
        assert resp.data["likes_count"] == 1
