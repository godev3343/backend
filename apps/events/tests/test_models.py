from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.db import IntegrityError
from django.utils.timezone import now

from apps.events.models import Event
from apps.places.tests.factories import PlaceFactory


@pytest.mark.django_db
class TestEventConstraints:
    def test_requires_place_or_location(self) -> None:
        with pytest.raises(IntegrityError):
            Event.objects.create(
                title="No place no point",
                starts_at=now() + timedelta(days=1),
                place=None,
                location=None,
            )

    def test_place_only_ok(self) -> None:
        place = PlaceFactory()
        event = Event.objects.create(
            title="With place",
            starts_at=now() + timedelta(days=1),
            place=place,
            location=None,
        )
        assert event.pk

    def test_location_only_ok(self) -> None:
        event = Event.objects.create(
            title="With location",
            starts_at=now() + timedelta(days=1),
            place=None,
            location=Point(71.4187, 51.0908, srid=4326),
        )
        assert event.pk

    def test_ends_after_starts_ok(self) -> None:
        starts = now() + timedelta(days=1)
        event = Event.objects.create(
            title="Valid time range",
            starts_at=starts,
            ends_at=starts + timedelta(hours=2),
            location=Point(71.4187, 51.0908, srid=4326),
        )
        assert event.pk

    def test_ends_before_starts_fails(self) -> None:
        starts = now() + timedelta(days=1)
        with pytest.raises(IntegrityError):
            Event.objects.create(
                title="Inverted time",
                starts_at=starts,
                ends_at=starts - timedelta(hours=2),
                location=Point(71.4187, 51.0908, srid=4326),
            )

    def test_ends_equal_starts_fails(self) -> None:
        starts = now() + timedelta(days=1)
        with pytest.raises(IntegrityError):
            Event.objects.create(
                title="Equal time",
                starts_at=starts,
                ends_at=starts,
                location=Point(71.4187, 51.0908, srid=4326),
            )

    def test_ends_null_ok(self) -> None:
        event = Event.objects.create(
            title="No end time",
            starts_at=now() + timedelta(days=1),
            ends_at=None,
            location=Point(71.4187, 51.0908, srid=4326),
        )
        assert event.pk
