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
        # Локальный объект тоже синхронизирован
        # (см. user.points = ... в award())

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
        # Поинты начислены ровно один раз
        assert user.points == POINTS_BY_REASON[PointsReason.CHECKIN]

    def test_signup_no_ref_idempotent(self) -> None:
        """Без ref_id — уникальность по (user, reason), повтор → None."""
        user = UserFactory()
        first = PointsService.award(user=user, reason=PointsReason.SIGNUP)
        second = PointsService.award(user=user, reason=PointsReason.SIGNUP)
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

    def test_concurrent_awards_use_atomic_increment(self) -> None:
        """
        Симулируем то, что несколько award'ов работают через F() — то есть
        не читают значение в Python, а апдейтят в БД. Проверяем по очереди.
        """
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