from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import IntegrityError

from apps.places.models import PlaceVibe, PlaceVibeTag
from apps.places.tests.factories import PlaceFactory, PlaceVibeFactory


@pytest.mark.django_db
class TestPlaceVibe:
    def test_unique_per_place_and_tag(self) -> None:
        place = PlaceFactory()
        PlaceVibeFactory(place=place, tag=PlaceVibeTag.CALM, weight=Decimal("0.5"))
        with pytest.raises(IntegrityError):
            PlaceVibe.objects.create(
                place=place, tag=PlaceVibeTag.CALM, weight=Decimal("0.8")
            )

    def test_different_tags_same_place_allowed(self) -> None:
        place = PlaceFactory()
        PlaceVibeFactory(place=place, tag=PlaceVibeTag.CALM)
        PlaceVibeFactory(place=place, tag=PlaceVibeTag.ACTIVE)
        assert PlaceVibe.objects.filter(place=place).count() == 2

    def test_same_tag_different_places_allowed(self) -> None:
        p1 = PlaceFactory()
        p2 = PlaceFactory()
        PlaceVibeFactory(place=p1, tag=PlaceVibeTag.CALM)
        PlaceVibeFactory(place=p2, tag=PlaceVibeTag.CALM)
        assert PlaceVibe.objects.filter(tag=PlaceVibeTag.CALM).count() == 2
