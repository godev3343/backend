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

    def test_no_ref_duplicate_fails(self) -> None:
        """
        ref_id=None → constraint pointstx_idempotency_no_ref:
        уникальность по (user, reason). Повторная запись с теми же
        (user, reason, ref_id=None) должна падать.

        В pre-MVP ни один reason не используется с ref_id=None (всё событийное),
        но контракт модели его поддерживает — тест защищает constraint
        от случайного снятия при будущих миграциях.
        """
        user = UserFactory()
        PointsTransaction.objects.create(
            user=user, delta=5, reason=PointsReason.CHECKIN
        )
        with pytest.raises(IntegrityError):
            PointsTransaction.objects.create(
                user=user, delta=5, reason=PointsReason.CHECKIN
            )

    def test_no_ref_different_users_ok(self) -> None:
        """Constraint per-user: разные юзеры независимо."""
        u1 = UserFactory()
        u2 = UserFactory()
        PointsTransaction.objects.create(user=u1, delta=5, reason=PointsReason.CHECKIN)
        PointsTransaction.objects.create(user=u2, delta=5, reason=PointsReason.CHECKIN)
        assert PointsTransaction.objects.filter(
            reason=PointsReason.CHECKIN, ref_id__isnull=True
        ).count() == 2
