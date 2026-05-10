# apps/checkins/tests/factories.py
import factory
from django.contrib.gis.geos import Point
from factory.django import DjangoModelFactory

from apps.checkins.models import CheckIn
from apps.places.tests.factories import PlaceFactory
from apps.users.tests.factories import UserFactory


class CheckInFactory(DjangoModelFactory):
    class Meta:
        model = CheckIn

    user = factory.SubFactory(UserFactory)
    place = factory.SubFactory(PlaceFactory)
    location = factory.LazyFunction(lambda: Point(71.4187, 51.0908, srid=4326))
    comment = ""