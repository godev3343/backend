# apps/social/tests/test_models.py
from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.social.tests.factories import FriendshipFactory
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestFriendship:
    def test_create_directional(self) -> None:
        a = UserFactory()
        b = UserFactory()
        friendship = FriendshipFactory(from_user=a, to_user=b)
        assert friendship.status == "pending"

    def test_no_self_friendship(self) -> None:
        a = UserFactory()
        with pytest.raises(IntegrityError):
            FriendshipFactory(from_user=a, to_user=a)

    def test_duplicate_pair_fails(self) -> None:
        a = UserFactory()
        b = UserFactory()
        FriendshipFactory(from_user=a, to_user=b)
        with pytest.raises(IntegrityError):
            FriendshipFactory(from_user=a, to_user=b)

    def test_reverse_direction_allowed(self) -> None:
        """A → B и B → A — разные записи, обе допустимы."""
        a = UserFactory()
        b = UserFactory()
        FriendshipFactory(from_user=a, to_user=b)
        # Обратное направление — отдельная запись
        FriendshipFactory(from_user=b, to_user=a)
