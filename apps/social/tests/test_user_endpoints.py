"""Тесты FriendshipService — бизнес-логика на уровне сервиса."""
from __future__ import annotations

import pytest

from apps.social.models import Friendship, FriendshipStatus
from apps.social.services import FriendshipService
from apps.social.services.exceptions import (
    AlreadyFriends,
    FriendshipExists,
    FriendshipNotFound,
    NotRecipient,
    SelfFriendshipError,
    TargetUserNotFound,
    UserBlocked,
)
from apps.social.tests.factories import FriendshipFactory
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestSendRequest:
    def test_creates_pending(self) -> None:
        a, b = UserFactory(), UserFactory()
        f = FriendshipService.send_request(from_user=a, to_user_id=b.pk)
        assert f.status == FriendshipStatus.PENDING
        assert f.from_user_id == a.pk and f.to_user_id == b.pk

    def test_self_friendship_forbidden(self) -> None:
        a = UserFactory()
        with pytest.raises(SelfFriendshipError):
            FriendshipService.send_request(from_user=a, to_user_id=a.pk)

    def test_target_not_found(self) -> None:
        a = UserFactory()
        with pytest.raises(TargetUserNotFound):
            FriendshipService.send_request(from_user=a, to_user_id=999_999)

    def test_target_inactive_not_found(self) -> None:
        a = UserFactory()
        b = UserFactory(is_active=False)
        with pytest.raises(TargetUserNotFound):
            FriendshipService.send_request(from_user=a, to_user_id=b.pk)

    def test_duplicate_pending_fails(self) -> None:
        a, b = UserFactory(), UserFactory()
        FriendshipService.send_request(from_user=a, to_user_id=b.pk)
        with pytest.raises(FriendshipExists):
            FriendshipService.send_request(from_user=a, to_user_id=b.pk)

    def test_already_friends_fails(self) -> None:
        a, b = UserFactory(), UserFactory()
        FriendshipFactory(
            from_user=a, to_user=b, status=FriendshipStatus.ACCEPTED
        )
        with pytest.raises(AlreadyFriends):
            FriendshipService.send_request(from_user=a, to_user_id=b.pk)

    def test_reverse_already_friends_fails(self) -> None:
        """b → a accepted; a пытается отправить b — должен упасть."""
        a, b = UserFactory(), UserFactory()
        FriendshipFactory(
            from_user=b, to_user=a, status=FriendshipStatus.ACCEPTED
        )
        with pytest.raises(AlreadyFriends):
            FriendshipService.send_request(from_user=a, to_user_id=b.pk)

    def test_blocked_forbidden(self) -> None:
        a, b = UserFactory(), UserFactory()
        FriendshipFactory(
            from_user=b, to_user=a, status=FriendshipStatus.BLOCKED
        )
        with pytest.raises(UserBlocked):
            FriendshipService.send_request(from_user=a, to_user_id=b.pk)

    def test_counter_pending_auto_accepts(self) -> None:
        """b отправил a; теперь a отправляет b — должен авто-accept."""
        a, b = UserFactory(), UserFactory()
        FriendshipService.send_request(from_user=b, to_user_id=a.pk)

        f = FriendshipService.send_request(from_user=a, to_user_id=b.pk)
        assert f.status == FriendshipStatus.ACCEPTED
        assert f.from_user_id == b.pk and f.to_user_id == a.pk
        # И только одна запись на пару
        assert Friendship.objects.count() == 1


@pytest.mark.django_db
class TestAcceptRequest:
    def test_accept_changes_status(self) -> None:
        a, b = UserFactory(), UserFactory()
        f = FriendshipFactory(from_user=a, to_user=b)
        accepted = FriendshipService.accept_request(user=b, friendship_id=f.pk)
        assert accepted.status == FriendshipStatus.ACCEPTED

    def test_accept_by_sender_forbidden(self) -> None:
        a, b = UserFactory(), UserFactory()
        f = FriendshipFactory(from_user=a, to_user=b)
        with pytest.raises(NotRecipient):
            FriendshipService.accept_request(user=a, friendship_id=f.pk)

    def test_accept_nonexistent(self) -> None:
        a = UserFactory()
        with pytest.raises(FriendshipNotFound):
            FriendshipService.accept_request(user=a, friendship_id=999_999)

    def test_accept_already_accepted_is_idempotent(self) -> None:
        a, b = UserFactory(), UserFactory()
        f = FriendshipFactory(
            from_user=a, to_user=b, status=FriendshipStatus.ACCEPTED
        )
        result = FriendshipService.accept_request(user=b, friendship_id=f.pk)
        assert result.status == FriendshipStatus.ACCEPTED

    def test_accept_blocked_fails(self) -> None:
        a, b = UserFactory(), UserFactory()
        f = FriendshipFactory(
            from_user=a, to_user=b, status=FriendshipStatus.BLOCKED
        )
        with pytest.raises(FriendshipNotFound):
            FriendshipService.accept_request(user=b, friendship_id=f.pk)


@pytest.mark.django_db
class TestDeclineRequest:
    def test_decline_hard_deletes(self) -> None:
        a, b = UserFactory(), UserFactory()
        f = FriendshipFactory(from_user=a, to_user=b)
        FriendshipService.decline_request(user=b, friendship_id=f.pk)
        assert not Friendship.objects.filter(pk=f.pk).exists()

    def test_decline_allows_resend(self) -> None:
        """После decline можно снова отправить заявку."""
        a, b = UserFactory(), UserFactory()
        f = FriendshipFactory(from_user=a, to_user=b)
        FriendshipService.decline_request(user=b, friendship_id=f.pk)
        # Снова отправляем — должно сработать
        f2 = FriendshipService.send_request(from_user=a, to_user_id=b.pk)
        assert f2.status == FriendshipStatus.PENDING

    def test_decline_by_sender_forbidden(self) -> None:
        a, b = UserFactory(), UserFactory()
        f = FriendshipFactory(from_user=a, to_user=b)
        with pytest.raises(NotRecipient):
            FriendshipService.decline_request(user=a, friendship_id=f.pk)


@pytest.mark.django_db
class TestCancelRequest:
    def test_cancel_hard_deletes(self) -> None:
        a, b = UserFactory(), UserFactory()
        f = FriendshipFactory(from_user=a, to_user=b)
        FriendshipService.cancel_request(user=a, friendship_id=f.pk)
        assert not Friendship.objects.filter(pk=f.pk).exists()

    def test_cancel_by_recipient_forbidden(self) -> None:
        a, b = UserFactory(), UserFactory()
        f = FriendshipFactory(from_user=a, to_user=b)
        with pytest.raises(NotRecipient):
            FriendshipService.cancel_request(user=b, friendship_id=f.pk)


@pytest.mark.django_db
class TestRemoveFriend:
    def test_remove_outgoing_direction(self) -> None:
        a, b = UserFactory(), UserFactory()
        FriendshipFactory(
            from_user=a, to_user=b, status=FriendshipStatus.ACCEPTED
        )
        FriendshipService.remove_friend(user=a, other_user_id=b.pk)
        assert not Friendship.objects.exists()

    def test_remove_incoming_direction(self) -> None:
        a, b = UserFactory(), UserFactory()
        FriendshipFactory(
            from_user=b, to_user=a, status=FriendshipStatus.ACCEPTED
        )
        FriendshipService.remove_friend(user=a, other_user_id=b.pk)
        assert not Friendship.objects.exists()

    def test_remove_when_not_friends_fails(self) -> None:
        a, b = UserFactory(), UserFactory()
        with pytest.raises(FriendshipNotFound):
            FriendshipService.remove_friend(user=a, other_user_id=b.pk)

    def test_remove_pending_does_not_count(self) -> None:
        """Pending — не дружба, remove_friend не должен её удалять."""
        a, b = UserFactory(), UserFactory()
        FriendshipFactory(
            from_user=a, to_user=b, status=FriendshipStatus.PENDING
        )
        with pytest.raises(FriendshipNotFound):
            FriendshipService.remove_friend(user=a, other_user_id=b.pk)
        assert Friendship.objects.count() == 1


@pytest.mark.django_db
class TestListFriends:
    def test_lists_both_directions(self) -> None:
        a, b, c = UserFactory(), UserFactory(), UserFactory()
        # a → b accepted, c → a accepted
        FriendshipFactory(
            from_user=a, to_user=b, status=FriendshipStatus.ACCEPTED
        )
        FriendshipFactory(
            from_user=c, to_user=a, status=FriendshipStatus.ACCEPTED
        )
        # Pending не должен попасть
        d = UserFactory()
        FriendshipFactory(from_user=a, to_user=d)

        friends = list(FriendshipService.list_friends(user=a))
        friend_ids = {u.pk for u in friends}
        assert friend_ids == {b.pk, c.pk}


@pytest.mark.django_db
class TestIsFriends:
    def test_is_friends_either_direction(self) -> None:
        a, b = UserFactory(), UserFactory()
        FriendshipFactory(
            from_user=a, to_user=b, status=FriendshipStatus.ACCEPTED
        )
        assert FriendshipService.is_friends(user_a_id=a.pk, user_b_id=b.pk)
        assert FriendshipService.is_friends(user_a_id=b.pk, user_b_id=a.pk)

    def test_pending_is_not_friends(self) -> None:
        a, b = UserFactory(), UserFactory()
        FriendshipFactory(from_user=a, to_user=b)
        assert not FriendshipService.is_friends(
            user_a_id=a.pk, user_b_id=b.pk
        )

    def test_self_is_not_friend(self) -> None:
        a = UserFactory()
        assert not FriendshipService.is_friends(user_a_id=a.pk, user_b_id=a.pk)