"""Place.city — миграция и дефолт."""

from __future__ import annotations

import pytest

from apps.places.models import City, Place
from apps.places.tests.factories import PlaceFactory


@pytest.mark.django_db
class TestPlaceCity:
    def test_default_city_is_astana(self) -> None:
        p = PlaceFactory()
        assert p.city == City.ASTANA

    def test_filter_by_city(self) -> None:
        PlaceFactory.create_batch(3)
        assert Place.objects.filter(city=City.ASTANA).count() == 3
        assert Place.objects.filter(city="non_existent").count() == 0
