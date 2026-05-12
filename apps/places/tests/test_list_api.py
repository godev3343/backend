"""Тесты GET /api/places."""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse

from apps.places.models import PlaceVibeTag
from apps.places.tests.factories import (
    PlaceCategoryFactory,
    PlaceFactory,
    PlaceVibeFactory,
)


@pytest.fixture
def list_url() -> str:
    return reverse("places:list")


@pytest.mark.django_db
class TestPlaceList:
    def test_returns_places_in_bbox(self, api_client, list_url) -> None:
        # Внутри bbox
        inside = PlaceFactory(
            location=Point(71.42, 51.09, srid=4326),
            is_verified=True,
        )
        # Снаружи (далеко)
        PlaceFactory(
            location=Point(75.00, 55.00, srid=4326),
            is_verified=True,
        )

        bbox = "71.40,51.08,71.45,51.10"
        resp = api_client.get(list_url, {"bbox": bbox})
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.data]
        assert ids == [inside.id]

    def test_excludes_unverified(self, api_client, list_url) -> None:
        PlaceFactory(
            location=Point(71.42, 51.09, srid=4326),
            is_verified=False,
        )
        resp = api_client.get(list_url, {"bbox": "71.40,51.08,71.45,51.10"})
        assert resp.status_code == 200
        assert resp.data == []

    def test_vibe_filter_or_semantics(self, api_client, list_url) -> None:
        # 'calm' и 'romantic' — два разных места; фильтр vibe=calm,romantic
        # должен вернуть оба (OR).
        loc = Point(71.42, 51.09, srid=4326)
        p1 = PlaceFactory(location=loc, is_verified=True)
        PlaceVibeFactory(place=p1, tag=PlaceVibeTag.CALM, weight=Decimal("0.9"))

        p2 = PlaceFactory(location=loc, is_verified=True)
        PlaceVibeFactory(place=p2, tag=PlaceVibeTag.ROMANTIC, weight=Decimal("0.8"))

        p3 = PlaceFactory(location=loc, is_verified=True)
        PlaceVibeFactory(place=p3, tag=PlaceVibeTag.GAMING, weight=Decimal("0.5"))

        resp = api_client.get(
            list_url,
            {"bbox": "71.40,51.08,71.45,51.10", "vibe": "calm,romantic"},
        )
        assert resp.status_code == 200
        ids = sorted(p["id"] for p in resp.data)
        assert ids == sorted([p1.id, p2.id])

    def test_category_filter(self, api_client, list_url) -> None:
        cafe = PlaceCategoryFactory(slug="cafe")
        bar = PlaceCategoryFactory(slug="bar")
        loc = Point(71.42, 51.09, srid=4326)
        p_cafe = PlaceFactory(category=cafe, location=loc, is_verified=True)
        PlaceFactory(category=bar, location=loc, is_verified=True)

        resp = api_client.get(
            list_url,
            {"bbox": "71.40,51.08,71.45,51.10", "category": "cafe"},
        )
        assert resp.status_code == 200
        assert [p["id"] for p in resp.data] == [p_cafe.id]

    def test_primary_vibe_is_max_weight(self, api_client, list_url) -> None:
        loc = Point(71.42, 51.09, srid=4326)
        p = PlaceFactory(location=loc, is_verified=True)
        PlaceVibeFactory(place=p, tag=PlaceVibeTag.CALM, weight=Decimal("0.3"))
        PlaceVibeFactory(place=p, tag=PlaceVibeTag.MUSICAL, weight=Decimal("0.9"))
        PlaceVibeFactory(place=p, tag=PlaceVibeTag.ROMANTIC, weight=Decimal("0.5"))

        resp = api_client.get(list_url, {"bbox": "71.40,51.08,71.45,51.10"})
        assert resp.status_code == 200
        assert resp.data[0]["primary_vibe"] == "musical"

    def test_no_vibes_returns_null_primary(self, api_client, list_url) -> None:
        PlaceFactory(
            location=Point(71.42, 51.09, srid=4326),
            is_verified=True,
        )
        resp = api_client.get(list_url, {"bbox": "71.40,51.08,71.45,51.10"})
        assert resp.status_code == 200
        assert resp.data[0]["primary_vibe"] is None

    def test_missing_bbox_400(self, api_client, list_url) -> None:
        resp = api_client.get(list_url)
        assert resp.status_code == 400
        assert resp.data["code"] == "invalid_bbox"

    def test_invalid_vibe_400(self, api_client, list_url) -> None:
        resp = api_client.get(
            list_url,
            {"bbox": "71.40,51.08,71.45,51.10", "vibe": "wat"},
        )
        assert resp.status_code == 400
        assert resp.data["code"] == "invalid_vibe"

    def test_bbox_too_large_400(self, api_client, list_url) -> None:
        resp = api_client.get(list_url, {"bbox": "70.0,50.0,73.0,53.0"})
        assert resp.status_code == 400
        assert resp.data["code"] == "bbox_too_large"

    def test_limit_respected(self, api_client, list_url) -> None:
        loc = Point(71.42, 51.09, srid=4326)
        for _ in range(5):
            PlaceFactory(location=loc, is_verified=True)
        resp = api_client.get(
            list_url,
            {"bbox": "71.40,51.08,71.45,51.10", "limit": "3"},
        )
        assert resp.status_code == 200
        assert len(resp.data) == 3

    def test_anonymous_allowed(self, api_client, list_url) -> None:
        """Карта доступна без авторизации — критично для UX онбординга."""
        api_client.credentials()  # clear any auth
        PlaceFactory(
            location=Point(71.42, 51.09, srid=4326),
            is_verified=True,
        )
        resp = api_client.get(list_url, {"bbox": "71.40,51.08,71.45,51.10"})
        assert resp.status_code == 200