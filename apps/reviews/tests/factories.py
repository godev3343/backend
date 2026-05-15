import factory

from apps.places.tests.factories import PlaceFactory
from apps.reviews.models import Review
from apps.users.tests.factories import UserFactory


class ReviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Review

    user = factory.SubFactory(UserFactory)
    place = factory.SubFactory(PlaceFactory)
    rating = 5
    text = "Хорошее место"