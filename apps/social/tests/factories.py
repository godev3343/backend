import factory
from factory.django import DjangoModelFactory

from apps.social.models import Friendship, FriendshipStatus
from apps.users.tests.factories import UserFactory


class FriendshipFactory(DjangoModelFactory):
    class Meta:
        model = Friendship

    from_user = factory.SubFactory(UserFactory)
    to_user = factory.SubFactory(UserFactory)
    status = FriendshipStatus.PENDING