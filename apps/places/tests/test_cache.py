"""Тесты кэша списка мест и инвалидации через сигналы."""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.gis.geos import Point
from django.core.cache import cache
from django.urls import reverse

from apps.places.filters import parse_list_query
from apps.places.models import PlaceVibeTag
from apps.places.services.cache import (
    VERSION_KEY,
    build_list_cache_key,
    bump_version,
    get_version,
)
from apps.places.tests.factories import PlaceFactory, PlaceVibeFactory


class TestVersionCounter:
    def test_get_version_initial(self) -> None:
        assert get_version() == 1

    def test_bump_increments(self) -> None:
        get_version()  # init
        assert bump_version() == 2
        assert bump_version() == 3
        assert get_version() == 3

    def test_bump_when_no_key(self) -> None:
        # Симулируем flushall: ключа нет → bump создаёт = 1
        cache.delete(VERSION_KEY)
        result = bump_version()
        assert result == 1


class TestCacheKey:
    def test_key_includes_version(self) -> None:
        query = parse_list_query("71.0,51.0,71.5,51.5", "calm", None, "100")
        key_v1 = build_list_cache_key(query)
        bump_version()
        key_v2 = build_list_cache_key(query)
        assert key_v1 != key_v2

    def test_key_deterministic_for_same_query(self) -> None:
        q1 = parse_list_query("71.0,51.0,71.5,51.5", "calm,romantic", None, "100")
        q2 = parse_list_query("71.0,51.0,71.5,51.5", "romantic,calm", None, "100")
        assert build_list_cache_key(q1) == build_list_cache_key(q2)

    def test_bbox_rounded_in_key(self) -> None:
        # Два запроса с микро-различием → один и тот же ключ
        q1 = parse_list_query("71.0001,51.0001,71.5,51.5", None, None, None)
        q2 = parse_list_query("71.0002,51.0002,71.5,51.5", None, None, None)
        assert build_list_cache_key(q1) == build_list_cache_key(q2)


@pytest.mark.django_db
class TestSignalsInvalidateCache:
    def _hit_list(self, api_client) -> list:
        url = reverse("places:list")
        resp = api_client.get(url, {"bbox": "71.40,51.08,71.45,51.10"})
        assert resp.status_code == 200
        return resp.data

    def test_place_save_bumps_version(self, api_client) -> None:
        v1 = get_version()
        PlaceFactory(
            location=Point(71.42, 51.09, srid=4326),
            is_verified=True,
        )
        assert get_version() > v1

    def test_place_delete_bumps_version(self, api_client) -> None:
        place = PlaceFactory(
            location=Point(71.42, 51.09, srid=4326),
            is_verified=True,
        )
        v = get_version()
        place.delete()
        assert get_version() > v

    def test_vibe_save_bumps_version(self, api_client) -> None:
        place = PlaceFactory(
            location=Point(71.42, 51.09, srid=4326),
            is_verified=True,
        )
        v = get_version()
        PlaceVibeFactory(place=place, tag=PlaceVibeTag.CALM, weight=Decimal("0.5"))
        assert get_version() > v

    def test_new_place_appears_after_invalidation(self, api_client) -> None:
        # warm cache, пока пусто
        data1 = self._hit_list(api_client)
        assert data1 == []

        # Создаём место — сигнал должен сбросить версию
        PlaceFactory(
            location=Point(71.42, 51.09, srid=4326),
            is_verified=True,
        )

        # Второй запрос отдаёт новый список (другой cache key → miss → fresh data)
        data2 = self._hit_list(api_client)
        assert len(data2) == 1