# apps/social/tests/test_annotate_friendship_status.py
"""
Тесты annotate_friendship_status — проверка friendship_id annotation.

friendship_id — pk Friendship для pending_outgoing / pending_incoming,
null для friends / blocked / none / self. Нужен фронту, чтобы вызывать
endpoints accept / decline / cancel, которые принимают именно
Friendship.pk, а не user_id.

Сам friendship_status покрыт где-то ещё; здесь фокус только на id.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.social.models import Friendship, FriendshipStatus
from apps.social.services import annotate_friendship_status
from apps.users.tests.factories import UserFactory

User = get_user_model()


@pytest.mark.django_db
class TestFriendshipIdAnnotation:
    """friendship_id должен быть pk Friendship для pending, null иначе."""

    def test_pending_outgoing_has_id(self) -> None:
        viewer = UserFactory()
        other = UserFactory()
        f = Friendship.objects.create(
            from_user=viewer,
            to_user=other,
            status=FriendshipStatus.PENDING,
        )

        qs = annotate_friendship_status(
            User.objects.filter(pk=other.pk),
            viewer_id=viewer.pk,
        )
        user = qs.get()
        assert user.friendship_status == "pending_outgoing"
        assert user.friendship_id == f.pk

    def test_pending_incoming_has_id(self) -> None:
        viewer = UserFactory()
        other = UserFactory()
        f = Friendship.objects.create(
            from_user=other,
            to_user=viewer,
            status=FriendshipStatus.PENDING,
        )

        qs = annotate_friendship_status(
            User.objects.filter(pk=other.pk),
            viewer_id=viewer.pk,
        )
        user = qs.get()
        assert user.friendship_status == "pending_incoming"
        assert user.friendship_id == f.pk

    def test_friends_has_null_id(self) -> None:
        viewer = UserFactory()
        other = UserFactory()
        Friendship.objects.create(
            from_user=viewer,
            to_user=other,
            status=FriendshipStatus.ACCEPTED,
        )

        qs = annotate_friendship_status(
            User.objects.filter(pk=other.pk),
            viewer_id=viewer.pk,
        )
        user = qs.get()
        assert user.friendship_status == "friends"
        assert user.friendship_id is None

    def test_blocked_has_null_id(self) -> None:
        viewer = UserFactory()
        other = UserFactory()
        Friendship.objects.create(
            from_user=viewer,
            to_user=other,
            status=FriendshipStatus.BLOCKED,
        )

        qs = annotate_friendship_status(
            User.objects.filter(pk=other.pk),
            viewer_id=viewer.pk,
        )
        user = qs.get()
        assert user.friendship_status == "blocked"
        assert user.friendship_id is None

    def test_none_status_has_null_id(self) -> None:
        viewer = UserFactory()
        other = UserFactory()

        qs = annotate_friendship_status(
            User.objects.filter(pk=other.pk),
            viewer_id=viewer.pk,
        )
        user = qs.get()
        assert user.friendship_status == "none"
        assert user.friendship_id is None

    def test_self_has_null_id(self) -> None:
        viewer = UserFactory()
        qs = annotate_friendship_status(
            User.objects.filter(pk=viewer.pk),
            viewer_id=viewer.pk,
        )
        user = qs.get()
        assert user.friendship_status == "self"
        assert user.friendship_id is None

    def test_anonymous_viewer_null_id(self) -> None:
        """viewer_id=None → все юзеры получают status=none и id=null."""
        other = UserFactory()
        qs = annotate_friendship_status(
            User.objects.filter(pk=other.pk),
            viewer_id=None,
        )
        user = qs.get()
        assert user.friendship_status == "none"
        assert user.friendship_id is None

    def test_bulk_queryset_returns_correct_ids(self) -> None:
        """
        Annotate работает на queryset с несколькими юзерами —
        не теряем id и не подмешиваем чужие.
        """
        viewer = UserFactory()
        out_user = UserFactory()  # viewer → out_user, pending
        in_user = UserFactory()  # in_user → viewer, pending
        friend = UserFactory()  # accepted
        stranger = UserFactory()  # никакой связи

        f_out = Friendship.objects.create(
            from_user=viewer, to_user=out_user, status=FriendshipStatus.PENDING,
        )
        f_in = Friendship.objects.create(
            from_user=in_user, to_user=viewer, status=FriendshipStatus.PENDING,
        )
        Friendship.objects.create(
            from_user=viewer, to_user=friend, status=FriendshipStatus.ACCEPTED,
        )

        qs = annotate_friendship_status(
            User.objects.filter(
                pk__in=[out_user.pk, in_user.pk, friend.pk, stranger.pk],
            ),
            viewer_id=viewer.pk,
        )
        by_id = {u.pk: u for u in qs}

        assert by_id[out_user.pk].friendship_status == "pending_outgoing"
        assert by_id[out_user.pk].friendship_id == f_out.pk

        assert by_id[in_user.pk].friendship_status == "pending_incoming"
        assert by_id[in_user.pk].friendship_id == f_in.pk

        assert by_id[friend.pk].friendship_status == "friends"
        assert by_id[friend.pk].friendship_id is None

        assert by_id[stranger.pk].friendship_status == "none"
        assert by_id[stranger.pk].friendship_id is None