from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APIClient

from apps.events.tests.factories import EventFactory
from apps.places.tests.factories import PlaceFactory


@pytest.fixture
def api() -> APIClient:
    return APIClient()


def _list_url() -> str:
    return reverse("events:list")


def _detail_url(pk: int) -> str:
    return reverse("events:detail", kwargs={"pk": pk})


@pytest.mark.django_db
class TestEventList:
    def test_empty(self, api: APIClient) -> None:
        resp = api.get(_list_url())
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 0
        assert resp.data["results"] == []

    def test_default_period_includes_future_within_14d(self, api: APIClient) -> None:
        future = EventFactory(starts_at=now() + timedelta(days=7))
        resp = api.get(_list_url())
        assert resp.status_code == 200
        ids = [item["id"] for item in resp.data["results"]]
        assert future.id in ids

    def test_past_event_without_ends_at_excluded_by_default(
        self, api: APIClient
    ) -> None:
        EventFactory(starts_at=now() - timedelta(days=2))
        resp = api.get(_list_url())
        assert resp.data["count"] == 0

    def test_past_event_with_future_ends_at_included(self, api: APIClient) -> None:
        """Концерт начался вчера, длится до завтра — это активное событие."""
        ongoing = EventFactory(
            starts_at=now() - timedelta(days=1),
            ends_at=now() + timedelta(days=1),
        )
        resp = api.get(_list_url())
        ids = [item["id"] for item in resp.data["results"]]
        assert ongoing.id in ids

    def test_event_beyond_default_window_excluded(self, api: APIClient) -> None:
        EventFactory(starts_at=now() + timedelta(days=30))
        resp = api.get(_list_url())
        assert resp.data["count"] == 0

    def test_explicit_period(self, api: APIClient) -> None:
        far_future = EventFactory(starts_at=now() + timedelta(days=30))
        resp = api.get(
            _list_url(),
            {
                "from": (now() + timedelta(days=25)).isoformat(),
                "to": (now() + timedelta(days=35)).isoformat(),
            },
        )
        ids = [item["id"] for item in resp.data["results"]]
        assert far_future.id in ids

    def test_invalid_period_returns_400(self, api: APIClient) -> None:
        resp = api.get(
            _list_url(),
            {
                "from": (now() + timedelta(days=30)).isoformat(),
                "to": (now() + timedelta(days=10)).isoformat(),
            },
        )
        assert resp.status_code == 400
        assert resp.data["code"] == "invalid_period"

    def test_bbox_includes_inside(self, api: APIClient) -> None:
        inside = EventFactory(location=Point(71.4187, 51.0908, srid=4326))
        # bbox вокруг Астаны
        resp = api.get(_list_url(), {"bbox": "71.0,50.9,71.6,51.3"})
        ids = [item["id"] for item in resp.data["results"]]
        assert inside.id in ids

    def test_bbox_excludes_outside(self, api: APIClient) -> None:
        EventFactory(location=Point(76.9, 43.2, srid=4326))  # Алматы
        resp = api.get(_list_url(), {"bbox": "71.0,50.9,71.6,51.3"})  # Астана
        assert resp.data["count"] == 0

    def test_bbox_with_place_event_uses_denormalized_location(
        self, api: APIClient
    ) -> None:
        """Событие привязано к Place — bbox должен находить его через денормализованный Event.location."""
        place = PlaceFactory(location=Point(71.4187, 51.0908, srid=4326))
        event = EventFactory(place=place, location=None)
        # save() должен был скопировать place.location в event.location
        event.refresh_from_db()
        assert event.location is not None

        resp = api.get(_list_url(), {"bbox": "71.0,50.9,71.6,51.3"})
        ids = [item["id"] for item in resp.data["results"]]
        assert event.id in ids

    def test_invalid_bbox_returns_400(self, api: APIClient) -> None:
        resp = api.get(_list_url(), {"bbox": "garbage"})
        assert resp.status_code == 400
        assert resp.data["code"] == "invalid_bbox"

    def test_sorted_by_starts_at(self, api: APIClient) -> None:
        e_later = EventFactory(starts_at=now() + timedelta(days=5))
        e_sooner = EventFactory(starts_at=now() + timedelta(days=2))
        resp = api.get(_list_url())
        ids = [item["id"] for item in resp.data["results"]]
        assert ids == [e_sooner.id, e_later.id]

    def test_list_item_shape_with_place(self, api: APIClient) -> None:
        place = PlaceFactory(name="Coffee BU")
        event = EventFactory(place=place, location=None, title="Live jazz")
        resp = api.get(_list_url())
        item = resp.data["results"][0]
        assert item["id"] == event.id
        assert item["title"] == "Live jazz"
        assert item["place"] == {"id": place.id, "name": "Coffee BU"}
        assert item["location"] == {"lat": pytest.approx(51.0908), "lng": pytest.approx(71.4187)}

    def test_list_item_shape_without_place(self, api: APIClient) -> None:
        EventFactory(
            place=None,
            location=Point(71.5, 51.2, srid=4326),
            title="Pop-up market",
        )
        resp = api.get(_list_url())
        item = resp.data["results"][0]
        assert item["place"] is None
        assert item["location"] == {"lat": 51.2, "lng": 71.5}

    def test_anonymous_access_allowed(self, api: APIClient) -> None:
        EventFactory()
        resp = api.get(_list_url())
        # Никакой аутентификации не передавали — должно работать.
        assert resp.status_code == 200


@pytest.mark.django_db
class TestEventDetail:
    def test_404_for_missing(self, api: APIClient) -> None:
        resp = api.get(_detail_url(999_999))
        assert resp.status_code == 404
        assert resp.data["code"] == "event_not_found"

    def test_returns_full_shape(self, api: APIClient) -> None:
        place = PlaceFactory(name="Astana Arena")
        event = EventFactory(
            place=place,
            location=None,
            title="Show",
            description="Description text",
            starts_at=now() + timedelta(days=1),
        )
        resp = api.get(_detail_url(event.id))
        assert resp.status_code == 200
        assert resp.data["id"] == event.id
        assert resp.data["title"] == "Show"
        assert resp.data["description"] == "Description text"
        assert resp.data["place"] == {"id": place.id, "name": "Astana Arena"}
        assert resp.data["location"] is not None
        assert "created_at" in resp.data
        assert "starts_at" in resp.data

    def test_past_event_still_returned(self, api: APIClient) -> None:
        """Detail не фильтрует по периоду — карточка прошедшего ивента доступна по прямой ссылке."""
        event = EventFactory(starts_at=now() - timedelta(days=30))
        resp = api.get(_detail_url(event.id))
        assert resp.status_code == 200