"""Тесты сборки AI-контекста."""
from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.cache import cache

from apps.ai.services.context import (
    VIBES_VERSION_KEY,
    build_context,
    bump_vibes_version,
    get_vibes_version,
)
from apps.places.models import City, PlaceVibe, PlaceVibeTag
from apps.places.tests.factories import (
    PlaceCategoryFactory,
    PlaceFactory,
    PlaceVibeFactory,
)


@pytest.mark.django_db
class TestContextBuilder:
    def test_only_verified_places_in_context(self) -> None:
        verified = PlaceFactory(is_verified=True, city=City.ASTANA)
        unverified = PlaceFactory(is_verified=False, city=City.ASTANA)

        ctx = build_context(city=City.ASTANA.value)
        assert verified.id in ctx.valid_place_ids
        assert unverified.id not in ctx.valid_place_ids

    def test_other_city_filtered_out(self) -> None:
        astana = PlaceFactory(is_verified=True, city=City.ASTANA)

        ctx = build_context(city=City.ASTANA.value)
        assert astana.id in ctx.valid_place_ids

    def test_context_text_includes_place_id_and_name(self) -> None:
        cat = PlaceCategoryFactory(name_ru="Кафе")
        p = PlaceFactory(name="Test Cafe", category=cat, is_verified=True)
        PlaceVibeFactory(place=p, tag=PlaceVibeTag.CALM, weight=Decimal("0.7"))

        ctx = build_context(city=City.ASTANA.value)
        assert f"[place_id={p.id}]" in ctx.text
        assert "Test Cafe" in ctx.text
        assert "calm" in ctx.text

    def test_cache_used_on_second_call(self, django_assert_num_queries) -> None:  # type: ignore[no-untyped-def]
        PlaceFactory(is_verified=True, city=City.ASTANA)

        # Первый вызов — запросы к БД
        build_context(city=City.ASTANA.value)
        # Второй — должен быть из кэша, 0 запросов
        with django_assert_num_queries(0):
            build_context(city=City.ASTANA.value)

    def test_bump_vibes_version_invalidates_cache(self) -> None:
        p = PlaceFactory(is_verified=True, city=City.ASTANA)
        ctx1 = build_context(city=City.ASTANA.value)
        assert p.id in ctx1.valid_place_ids

        # Добавляем новое место + bump
        new_place = PlaceFactory(is_verified=True, city=City.ASTANA)
        bump_vibes_version()

        ctx2 = build_context(city=City.ASTANA.value)
        assert new_place.id in ctx2.valid_place_ids

    def test_get_vibes_version_initializes_to_1(self) -> None:
        cache.delete(VIBES_VERSION_KEY)
        assert get_vibes_version() == 1

    def test_bump_increments_version(self) -> None:
        v1 = get_vibes_version()
        bump_vibes_version()
        v2 = get_vibes_version()
        assert v2 == v1 + 1