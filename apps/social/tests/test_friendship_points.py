"""
Поинты за дружбу — интеграционный тест через FriendshipService.

Семантика (EPIC 9): на момент перехода в ACCEPTED обоим юзерам начисляется
+5 (PointsReason.FRIEND_ADDED, ref_id=friendship.pk).

Покрытие:
- обычный flow send→accept: обоим начислено
- counter-pending auto-accept в send_request: обоим начислено
- повторный accept уже accepted: не дублирует
- decline + новая accept (новый friendship.pk) — начисляется снова
- decline без accept: поинтов нет
"""

from __future__ import annotations

import pytest

from apps.gamification.models import PointsReason, PointsTransaction
from apps.social.models import FriendshipStatus
from apps.social.services import FriendshipService
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestFriendshipAwardsPoints:
    def test_accept_awards_both_users(self) -> None:
        a = UserFactory()
        b = UserFactory()
        f = FriendshipService.send_request(from_user=a, to_user_id=b.pk)
        FriendshipService.accept_request(user=b, friendship_id=f.pk)

        a.refresh_from_db()
        b.refresh_from_db()
        assert a.points == 5
        assert b.points == 5

        a_tx = PointsTransaction.objects.filter(
            user=a, reason=PointsReason.FRIEND_ADDED, ref_id=f.pk
        )
        b_tx = PointsTransaction.objects.filter(
            user=b, reason=PointsReason.FRIEND_ADDED, ref_id=f.pk
        )
        assert a_tx.count() == 1
        assert b_tx.count() == 1

    def test_counter_pending_auto_accept_awards_both(self) -> None:
        """
        b отправил a; a отправляет b → авто-accept в send_request.
        Обоим +5.
        """
        a = UserFactory()
        b = UserFactory()
        f = FriendshipService.send_request(from_user=b, to_user_id=a.pk)
        # a отправляет b — встречная pending → автоматически accept
        result = FriendshipService.send_request(from_user=a, to_user_id=b.pk)
        assert result.pk == f.pk
        assert result.status == FriendshipStatus.ACCEPTED

        a.refresh_from_db()
        b.refresh_from_db()
        assert a.points == 5
        assert b.points == 5

    def test_repeated_accept_does_not_duplicate(self) -> None:
        """Повторный accept уже-accepted — не начисляет второй раз."""
        a = UserFactory()
        b = UserFactory()
        f = FriendshipService.send_request(from_user=a, to_user_id=b.pk)
        FriendshipService.accept_request(user=b, friendship_id=f.pk)
        FriendshipService.accept_request(user=b, friendship_id=f.pk)

        a.refresh_from_db()
        b.refresh_from_db()
        assert a.points == 5
        assert b.points == 5
        assert (
            PointsTransaction.objects.filter(reason=PointsReason.FRIEND_ADDED).count() == 2
        )  # по одной на юзера

    def test_decline_does_not_award(self) -> None:
        a = UserFactory()
        b = UserFactory()
        f = FriendshipService.send_request(from_user=a, to_user_id=b.pk)
        FriendshipService.decline_request(user=b, friendship_id=f.pk)

        a.refresh_from_db()
        b.refresh_from_db()
        assert a.points == 0
        assert b.points == 0
        assert PointsTransaction.objects.filter(reason=PointsReason.FRIEND_ADDED).count() == 0

    def test_decline_then_accept_awards_fresh(self) -> None:
        """
        Pre-MVP контракт: после decline новая accept = новый friendship.pk =
        новое начисление. В Этапе 1 (антифрод) пересмотрим.
        """
        a = UserFactory()
        b = UserFactory()
        f1 = FriendshipService.send_request(from_user=a, to_user_id=b.pk)
        FriendshipService.decline_request(user=b, friendship_id=f1.pk)

        f2 = FriendshipService.send_request(from_user=a, to_user_id=b.pk)
        FriendshipService.accept_request(user=b, friendship_id=f2.pk)

        a.refresh_from_db()
        b.refresh_from_db()
        assert a.points == 5
        assert b.points == 5
        assert PointsTransaction.objects.filter(reason=PointsReason.FRIEND_ADDED).count() == 2
