"""Тесты PointsService.award."""
from __future__ import annotations

import pytest

from apps.gamification.models import PointsReason, PointsTransaction
from apps.gamification.services import POINTS_BY_REASON, PointsService
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestAward:
    def test_creates_transaction(self) -> None:
        user = UserFactory()
        tx = PointsService.award(
            user=user,
            reason=PointsReason.CHECKIN,
            ref_type="checkin",
            ref_id=1,
        )
        assert tx is not None
        assert tx.delta == POINTS_BY_REASON[PointsReason.CHECKIN]
        assert tx.user_id == user.pk

    def test_increments_user_points(self) -> None:
        user = UserFactory()
        starting = user.points
        PointsService.award(
            user=user,
            reason=PointsReason.CHECKIN,
            ref_type="checkin",
            ref_id=1,
        )
        user.refresh_from_db()
        assert user.points == starting + POINTS_BY_REASON[PointsReason.CHECKIN]

    def test_duplicate_ref_returns_none(self) -> None:
        user = UserFactory()
        first = PointsService.award(
            user=user, reason=PointsReason.CHECKIN, ref_type="checkin", ref_id=1
        )
        second = PointsService.award(
            user=user, reason=PointsReason.CHECKIN, ref_type="checkin", ref_id=1
        )
        assert first is not None
        assert second is None
        assert PointsTransaction.objects.filter(user=user).count() == 1
        user.refresh_from_db()
        assert user.points == POINTS_BY_REASON[PointsReason.CHECKIN]

    def test_no_ref_idempotent(self) -> None:
        """
        ref_id=None → уникальность по (user, reason).
        Повторный award с теми же (user, reason) возвращает None.

        Сейчас в pre-MVP ни одно начисление не использует ref_id=None
        (все события — CHECKIN/FIRST_CHECKIN/FRIEND_ADDED — событийные),
        но контракт сервиса это поддерживает, и тест защищает его.
        """
        user = UserFactory()
        first = PointsService.award(user=user, reason=PointsReason.CHECKIN)
        second = PointsService.award(user=user, reason=PointsReason.CHECKIN)
        assert first is not None
        assert second is None

    def test_different_refs_both_award(self) -> None:
        user = UserFactory()
        PointsService.award(
            user=user, reason=PointsReason.CHECKIN, ref_type="checkin", ref_id=1
        )
        PointsService.award(
            user=user, reason=PointsReason.CHECKIN, ref_type="checkin", ref_id=2
        )
        user.refresh_from_db()
        assert user.points == 2 * POINTS_BY_REASON[PointsReason.CHECKIN]

    def test_unknown_reason_raises(self) -> None:
        user = UserFactory()
        with pytest.raises(ValueError):
            PointsService.award(user=user, reason="unknown_reason")

    def test_signup_reason_no_longer_valid(self) -> None:
        """SIGNUP вырезали в EPIC 9 (нет в бизнес-плане, нигде не вызывался)."""
        user = UserFactory()
        with pytest.raises(ValueError):
            PointsService.award(user=user, reason="signup")

    def test_referral_reason_no_longer_valid(self) -> None:
        """REFERRAL отложен до Этапа 1 (нужна вся реферальная инфраструктура)."""
        user = UserFactory()
        with pytest.raises(ValueError):
            PointsService.award(user=user, reason="referral")

    def test_concurrent_awards_use_atomic_increment(self) -> None:
        """Несколько award'ов через F() — БД-инкремент, не Python-read."""
        user = UserFactory()
        for i in range(5):
            PointsService.award(
                user=user,
                reason=PointsReason.CHECKIN,
                ref_type="checkin",
                ref_id=i,
            )
        user.refresh_from_db()
        assert user.points == 5 * POINTS_BY_REASON[PointsReason.CHECKIN]


@pytest.mark.django_db
class TestFriendAddedReason:
    """Минимальный smoke-test для нового reason. Полноценное покрытие
    flow дружбы — в apps/social/tests/test_friendship_points.py."""

    def test_friend_added_awards_5(self) -> None:
        user = UserFactory()
        tx = PointsService.award(
            user=user,
            reason=PointsReason.FRIEND_ADDED,
            ref_type="friendship",
            ref_id=1,
        )
        assert tx is not None
        assert tx.delta == 5
        user.refresh_from_db()
        assert user.points == 5

    def test_friend_added_idempotent_per_friendship(self) -> None:
        user = UserFactory()
        PointsService.award(
            user=user, reason=PointsReason.FRIEND_ADDED,
            ref_type="friendship", ref_id=1,
        )
        # Дубликат на ту же friendship — не начисляется.
        second = PointsService.award(
            user=user, reason=PointsReason.FRIEND_ADDED,
            ref_type="friendship", ref_id=1,
        )
        assert second is None
        user.refresh_from_db()
        assert user.points == 5