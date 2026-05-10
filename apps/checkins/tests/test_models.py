# apps/places/tests/test_models.py
from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.gis.geos import Point
from django.db import IntegrityError

from apps.places.models import PlaceVibeTag
from apps.places.tests.factories import PlaceFactory, PlaceVibeFactory


@pytest.mark.django_db
class TestPlace:
    def test_create_with_point(self) -> None:
        place = PlaceFactory(location=Point(71.4, 51.1, srid=4326))
        assert place.location.x == pytest.approx(71.4)
        assert place.location.y == pytest.approx(51.1)
        assert place.location.srid == 4326

    def test_default_not_verified(self) -> None:
        place = PlaceFactory()
        assert place.is_verified is False


@pytest.mark.django_db
class TestPlaceVibe:
    def test_unique_place_tag(self) -> None:
        place = PlaceFactory()
        PlaceVibeFactory(place=place, tag=PlaceVibeTag.CALM, weight=Decimal("0.5"))
        with pytest.raises(IntegrityError):
            PlaceVibeFactory(place=place, tag=PlaceVibeTag.CALM, weight=Decimal("0.7"))

    def test_different_tags_allowed(self) -> None:
        place = PlaceFactory()
        PlaceVibeFactory(place=place, tag=PlaceVibeTag.CALM)
        PlaceVibeFactory(place=place, tag=PlaceVibeTag.ACTIVE)