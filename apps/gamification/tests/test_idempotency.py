from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.gamification.models import PointsReason, PointsTransaction
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestPointsTransactionIdempotency:
    def test_duplicate_with_ref_fails(self) -> None:
        """Повторное событие с тем же ref должно падать на UniqueConstraint."""
        user = UserFactory()
        PointsTransaction.objects.create(
            user=user,
            delta=5,
            reason=PointsReason.CHECKIN,
            ref_type="checkin",
            ref_id=42,
        )
        with pytest.raises(IntegrityError):
            PointsTransaction.objects.create(
                user=user,
                delta=5,
                reason=PointsReason.CHECKIN,
                ref_type="checkin",
                ref_id=42,
            )

    def test_different_ref_id_ok(self) -> None:
        user = UserFactory()
        PointsTransaction.objects.create(
            user=user,
            delta=5,
            reason=PointsReason.CHECKIN,
            ref_type="checkin",
            ref_id=1,
        )
        PointsTransaction.objects.create(
            user=user,
            delta=5,
            reason=PointsReason.CHECKIN,
            ref_type="checkin",
            ref_id=2,
        )
        assert PointsTransaction.objects.filter(user=user).count() == 2

    def test_different_users_same_ref_ok(self) -> None:
        u1 = UserFactory()
        u2 = UserFactory()
        for u in (u1, u2):
            PointsTransaction.objects.create(
                user=u,
                delta=5,
                reason=PointsReason.CHECKIN,
                ref_type="checkin",
                ref_id=42,
            )
        assert PointsTransaction.objects.count() == 2

    def test_signup_duplicate_fails(self) -> None:
        """Для одноразовых причин (signup) — ref_id NULL, уникальность по (user, reason)."""
        user = UserFactory()
        PointsTransaction.objects.create(
            user=user, delta=10, reason=PointsReason.SIGNUP
        )
        with pytest.raises(IntegrityError):
            PointsTransaction.objects.create(
                user=user, delta=10, reason=PointsReason.SIGNUP
            )

    def test_signup_different_users_ok(self) -> None:
        u1 = UserFactory()
        u2 = UserFactory()
        PointsTransaction.objects.create(user=u1, delta=10, reason=PointsReason.SIGNUP)
        PointsTransaction.objects.create(user=u2, delta=10, reason=PointsReason.SIGNUP)
        assert PointsTransaction.objects.filter(reason=PointsReason.SIGNUP).count() == 2
