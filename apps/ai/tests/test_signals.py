"""Сигналы инвалидации AI-контекста."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.cache import cache

from apps.ai.services.context import VIBES_VERSION_KEY, get_vibes_version
from apps.places.models import PlaceVibeTag
from apps.places.tests.factories import PlaceFactory, PlaceVibeFactory


@pytest.mark.django_db
class TestAiSignals:
    def test_vibe_save_bumps_version(self) -> None:
        cache.set(VIBES_VERSION_KEY, 5)
        place = PlaceFactory()
        # Создание вайба — должен дёрнуться post_save сигнал
        PlaceVibeFactory(place=place, tag=PlaceVibeTag.CALM, weight=Decimal("0.5"))
        assert get_vibes_version() > 5

    def test_vibe_delete_bumps_version(self) -> None:
        place = PlaceFactory()
        vibe = PlaceVibeFactory(place=place)
        cache.set(VIBES_VERSION_KEY, 10)
        vibe.delete()
        assert get_vibes_version() > 10

    def test_place_save_bumps_version(self) -> None:
        cache.set(VIBES_VERSION_KEY, 3)
        PlaceFactory()
        assert get_vibes_version() > 3
