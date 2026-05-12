# apps/checkins/tests/test_checkin_api.py
"""API-тесты для POST /api/checkins и GET /api/checkins/me."""
from __future__ import annotations

import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse

from apps.checkins.models import CheckIn
from apps.checkins.tests.factories import CheckInFactory
from apps.places.tests.factories import PlaceFactory


PLACE_LAT, PLACE_LNG = 51.0908, 71.4187


@pytest.fixture
def place(db):  # type: ignore[no-untyped-def]
    return PlaceFactory(
        location=Point(PLACE_LNG, PLACE_LAT, srid=4326),
        is_verified=True,
    )


@pytest.mark.django_db
class TestCreateCheckInAPI:
    def test_creates_201(self, authed_client, place) -> None:  # type: ignore[no-untyped-def]
        url = reverse("checkins:create")
        resp = authed_client.post(
            url,
            data={
                "place_id": place.pk,
                "latitude": PLACE_LAT,
                "longitude": PLACE_LNG,
                "comment": "great spot",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.data
        assert resp.data["comment"] == "great spot"
        assert resp.data["likes_count"] == 0
        assert resp.data["is_liked"] is None  # context.liked_ids не передан

    def test_too_far_400(self, authed_client, place) -> None:  # type: ignore[no-untyped-def]
        url = reverse("checkins:create")
        resp = authed_client.post(
            url,
            data={
                "place_id": place.pk,
                "latitude": PLACE_LAT + 1.0,
                "longitude": PLACE_LNG,
            },
            format="json",
        )
        assert resp.status_code == 400
        assert resp.data["code"] == "too_far_from_place"

    def test_unauthenticated_401(self, api_client, place) -> None:  # type: ignore[no-untyped-def]
        url = reverse("checkins:create")
        resp = api_client.post(
            url,
            data={
                "place_id": place.pk,
                "latitude": PLACE_LAT,
                "longitude": PLACE_LNG,
            },
            format="json",
        )
        assert resp.status_code == 401

    def test_invalid_coords_400(self, authed_client, place) -> None:  # type: ignore[no-untyped-def]
        url = reverse("checkins:create")
        resp = authed_client.post(
            url,
            data={
                "place_id": place.pk,
                "latitude": 95.0,
                "longitude": PLACE_LNG,
            },
            format="json",
        )
        # Поле-level валидация в сериализаторе ловит → 400
        assert resp.status_code == 400

    def test_place_not_found_404(self, authed_client) -> None:  # type: ignore[no-untyped-def]
        url = reverse("checkins:create")
        resp = authed_client.post(
            url,
            data={
                "place_id": 999_999,
                "latitude": PLACE_LAT,
                "longitude": PLACE_LNG,
            },
            format="json",
        )
        assert resp.status_code == 404
        assert resp.data["code"] == "place_not_found"


@pytest.mark.django_db
class TestMyCheckInsAPI:
    def test_returns_own_only(self, authed_client, user, another_user) -> None:  # type: ignore[no-untyped-def]
        # 2 своих, 1 чужой
        mine_1 = CheckInFactory(user=user)
        mine_2 = CheckInFactory(user=user)
        CheckInFactory(user=another_user)

        url = reverse("checkins:me")
        resp = authed_client.get(url)
        assert resp.status_code == 200

        results = resp.data["results"]
        ids = {item["id"] for item in results}
        assert ids == {mine_1.pk, mine_2.pk}

    def test_pagination_shape(self, authed_client, user) -> None:  # type: ignore[no-untyped-def]
        for _ in range(3):
            CheckInFactory(user=user)
        url = reverse("checkins:me")
        resp = authed_client.get(url)
        # DRF CursorPagination shape
        assert "results" in resp.data
        assert "next" in resp.data
        assert "previous" in resp.data
        assert len(resp.data["results"]) == 3

    def test_unauthenticated_401(self, api_client) -> None:  # type: ignore[no-untyped-def]
        url = reverse("checkins:me")
        resp = api_client.get(url)
        assert resp.status_code == 401