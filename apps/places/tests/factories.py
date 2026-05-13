# apps/places/tests/factories.py
from decimal import Decimal

import factory
from django.contrib.gis.geos import Point
from factory.django import DjangoModelFactory

from apps.places.models import Place, PlaceCategory, PlaceVibe, PlaceVibeTag


class PlaceCategoryFactory(DjangoModelFactory):
    class Meta:
        model = PlaceCategory
        django_get_or_create = ("slug",)

    slug = factory.Sequence(lambda n: f"cat-{n}")
    name_ru = factory.Faker("word", locale="ru_RU")


class PlaceFactory(DjangoModelFactory):
    class Meta:
        model = Place

    name = factory.Faker("company")
    category = factory.SubFactory(PlaceCategoryFactory)
    location = factory.LazyFunction(lambda: Point(71.4187, 51.0908, srid=4326))
    address = factory.Faker("address")


class PlaceVibeFactory(DjangoModelFactory):
    class Meta:
        model = PlaceVibe

    place = factory.SubFactory(PlaceFactory)
    tag = PlaceVibeTag.CALM
    weight = Decimal("0.5")
