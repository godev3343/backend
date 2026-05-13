"""Тесты GET /api/places/{id}."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.gis.geos import Point
from django.urls import reverse

from apps.places.models import PlaceVibeTag
from apps.places.tests.factories import PlaceFactory, PlaceVibeFactory


@pytest.mark.django_db
class TestPlaceDetail:
    def test_returns_full_payload(self, api_client) -> None:
        place = PlaceFactory(
            location=Point(71.42, 51.09, srid=4326),
            address="ул. Кенесары 10",
            phone="+77001112233",
            description="A cozy spot",
            is_verified=True,
        )
        PlaceVibeFactory(place=place, tag=PlaceVibeTag.CALM, weight=Decimal("0.7"))
        PlaceVibeFactory(place=place, tag=PlaceVibeTag.ROMANTIC, weight=Decimal("0.9"))

        url = reverse("places:detail", kwargs={"pk": place.id})
        resp = api_client.get(url)
        assert resp.status_code == 200

        body = resp.data
        assert body["id"] == place.id
        assert body["name"] == place.name
        assert body["address"] == "ул. Кенесары 10"
        assert body["phone"] == "+77001112233"
        assert body["lat"] == pytest.approx(51.09)
        assert body["lng"] == pytest.approx(71.42)

        # Vibes отсортированы по weight desc
        vibe_tags = [v["tag"] for v in body["vibes"]]
        assert vibe_tags == ["romantic", "calm"]

    def test_404_when_missing(self, api_client) -> None:
        url = reverse("places:detail", kwargs={"pk": 999999})
        resp = api_client.get(url)
        assert resp.status_code == 404
        assert resp.data["code"] == "place_not_found"

    def test_no_n_plus_one(self, api_client, django_assert_num_queries) -> None:
        place = PlaceFactory(
            location=Point(71.42, 51.09, srid=4326),
            is_verified=True,
        )
        for tag in (PlaceVibeTag.CALM, PlaceVibeTag.ROMANTIC, PlaceVibeTag.MUSICAL):
            PlaceVibeFactory(place=place, tag=tag, weight=Decimal("0.5"))

        url = reverse("places:detail", kwargs={"pk": place.id})

        # Ровно 4 запроса:
        # 1) SELECT Place + JOIN category
        # 2) Prefetch vibes
        # 3) Prefetch photos + JOIN asset (MediaAsset)
        # 4) recent_checkins SELECT + JOIN user
        # AllowAny + AnonRateThrottle через cache — не делают DB-запросов.
        with django_assert_num_queries(4):
            resp = api_client.get(url)
            assert resp.status_code == 200

    def test_anonymous_allowed(self, api_client) -> None:
        place = PlaceFactory(
            location=Point(71.42, 51.09, srid=4326),
            is_verified=True,
        )
        api_client.credentials()
        url = reverse("places:detail", kwargs={"pk": place.id})
        resp = api_client.get(url)
        assert resp.status_code == 200

    def test_unverified_still_visible_by_id(self, api_client) -> None:
        """
        Detail-эндпоинт возвращает место даже если is_verified=False.
        Логика: в list — только верифицированные (карта), но прямую ссылку
        не блокируем (например, ссылка от админа на пре-модерацию).
        Если потом захотим скрывать — добавим filter(is_verified=True) в detail.
        """
        place = PlaceFactory(
            location=Point(71.42, 51.09, srid=4326),
            is_verified=False,
        )
        url = reverse("places:detail", kwargs={"pk": place.id})
        resp = api_client.get(url)
        assert resp.status_code == 200
