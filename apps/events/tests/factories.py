from __future__ import annotations

from datetime import timedelta

import factory
from django.contrib.gis.geos import Point
from django.utils.timezone import now
from factory.django import DjangoModelFactory

from apps.events.models import Event


class EventFactory(DjangoModelFactory):
    class Meta:
        model = Event

    title = factory.Sequence(lambda n: f"Event #{n}")
    description = ""
    # По умолчанию: место не указано, явные координаты Астаны.
    place = None
    location = factory.LazyFunction(lambda: Point(71.4187, 51.0908, srid=4326))
    starts_at = factory.LazyFunction(lambda: now() + timedelta(days=1))
    ends_at = None
    cover_url = ""