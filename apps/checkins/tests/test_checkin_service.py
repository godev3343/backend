"""
Тесты бизнес-логики CheckInService.

Покрытие по ТЗ 6.5:
- чек-ин дальше 100м → TooFarFromPlace
- чек-ин в пределах → создан + +5 поинтов
- первый чек-ин юзера в этом месте → +10 (FIRST_CHECKIN)
- повторный чек-ин в то же место → без FIRST_CHECKIN бонуса
"""

from __future__ import annotations

import pytest
from django.contrib.gis.geos import Point

from apps.checkins.models import CheckIn
from apps.checkins.services import CheckInService
from apps.checkins.services.exceptions import (
    InvalidLocation,
    PlaceNotFoundForCheckIn,
    TooFarFromPlace,
)
from apps.gamification.models import PointsReason, PointsTransaction
from apps.places.tests.factories import PlaceFactory
from apps.users.tests.factories import UserFactory

# Точка-якорь для всех тестов — Астана, Назарбаев-центр.
PLACE_LAT, PLACE_LNG = 51.0908, 71.4187


def _make_place():  # type: ignore[no-untyped-def]
    return PlaceFactory(
        location=Point(PLACE_LNG, PLACE_LAT, srid=4326),
        is_verified=True,
    )


@pytest.mark.django_db
class TestCreateCheckIn:
    def test_creates_within_range(self) -> None:
        user = UserFactory()
        place = _make_place()
        checkin = CheckInService.create(
            user=user,
            place_id=place.pk,
            latitude=PLACE_LAT,
            longitude=PLACE_LNG,
            comment="nice place",
        )
        assert checkin.user_id == user.pk
        assert checkin.place_id == place.pk
        assert checkin.comment == "nice place"
        assert CheckIn.objects.count() == 1

    def test_too_far_raises(self) -> None:
        user = UserFactory()
        place = _make_place()
        with pytest.raises(TooFarFromPlace):
            CheckInService.create(
                user=user,
                place_id=place.pk,
                latitude=PLACE_LAT + 1.0,
                longitude=PLACE_LNG,
            )
        assert CheckIn.objects.count() == 0

    def test_just_outside_100m_fails(self) -> None:
        """~150м к северу: 0.00135° по широте ≈ 150м."""
        user = UserFactory()
        place = _make_place()
        with pytest.raises(TooFarFromPlace):
            CheckInService.create(
                user=user,
                place_id=place.pk,
                latitude=PLACE_LAT + 0.00135,
                longitude=PLACE_LNG,
            )

    def test_just_inside_100m_ok(self) -> None:
        """~50м к северу — должен пройти."""
        user = UserFactory()
        place = _make_place()
        CheckInService.create(
            user=user,
            place_id=place.pk,
            latitude=PLACE_LAT + 0.00045,
            longitude=PLACE_LNG,
        )
        assert CheckIn.objects.count() == 1

    def test_invalid_coords(self) -> None:
        user = UserFactory()
        place = _make_place()
        with pytest.raises(InvalidLocation):
            CheckInService.create(
                user=user,
                place_id=place.pk,
                latitude=95.0,
                longitude=PLACE_LNG,
            )

    def test_place_not_found(self) -> None:
        user = UserFactory()
        with pytest.raises(PlaceNotFoundForCheckIn):
            CheckInService.create(
                user=user,
                place_id=999_999,
                latitude=PLACE_LAT,
                longitude=PLACE_LNG,
            )


@pytest.mark.django_db
class TestPointsAwarding:
    """
    Семантика FIRST_CHECKIN — личная: "первый раз юзера в этом месте".
    Друзья не участвуют (изменено в EPIC 9 по бизнес-плану §5.1).
    """

    def test_first_checkin_awards_checkin_and_first_bonus(self) -> None:
        """Первый раз в месте → +5 (CHECKIN) и +10 (FIRST_CHECKIN)."""
        user = UserFactory()
        place = _make_place()
        CheckInService.create(user=user, place_id=place.pk, latitude=PLACE_LAT, longitude=PLACE_LNG)
        txs = list(PointsTransaction.objects.filter(user=user).order_by("created_at"))
        reasons = {tx.reason for tx in txs}
        assert reasons == {PointsReason.CHECKIN, PointsReason.FIRST_CHECKIN}
        user.refresh_from_db()
        assert user.points == 5 + 10

    def test_second_checkin_same_place_no_first_bonus(self) -> None:
        """Повторный чек-ин в то же место → только +5, без FIRST_CHECKIN."""
        user = UserFactory()
        place = _make_place()
        CheckInService.create(user=user, place_id=place.pk, latitude=PLACE_LAT, longitude=PLACE_LNG)
        CheckInService.create(user=user, place_id=place.pk, latitude=PLACE_LAT, longitude=PLACE_LNG)
        first_bonuses = PointsTransaction.objects.filter(
            user=user, reason=PointsReason.FIRST_CHECKIN
        )
        checkins = PointsTransaction.objects.filter(user=user, reason=PointsReason.CHECKIN)
        assert first_bonuses.count() == 1
        assert checkins.count() == 2
        user.refresh_from_db()
        # 5 (1-й чек-ин) + 10 (first bonus) + 5 (2-й чек-ин) = 20
        assert user.points == 20

    def test_first_checkin_independent_per_place(self) -> None:
        """Юзер чек-инится в разные места → FIRST_CHECKIN бонус за каждое."""
        user = UserFactory()
        place_a = _make_place()
        place_b = PlaceFactory(
            location=Point(PLACE_LNG + 0.5, PLACE_LAT + 0.5, srid=4326),
            is_verified=True,
        )
        CheckInService.create(
            user=user, place_id=place_a.pk, latitude=PLACE_LAT, longitude=PLACE_LNG
        )
        CheckInService.create(
            user=user,
            place_id=place_b.pk,
            latitude=PLACE_LAT + 0.5,
            longitude=PLACE_LNG + 0.5,
        )
        first_bonuses = PointsTransaction.objects.filter(
            user=user, reason=PointsReason.FIRST_CHECKIN
        )
        assert first_bonuses.count() == 2

    def test_first_checkin_independent_per_user(self) -> None:
        """
        a и b — оба впервые чек-инятся в одно место. Оба получают FIRST_CHECKIN.
        Бонус личный, не глобальный "первооткрыватель".
        """
        a = UserFactory()
        b = UserFactory()
        place = _make_place()
        CheckInService.create(user=a, place_id=place.pk, latitude=PLACE_LAT, longitude=PLACE_LNG)
        CheckInService.create(user=b, place_id=place.pk, latitude=PLACE_LAT, longitude=PLACE_LNG)
        assert (
            PointsTransaction.objects.filter(user=a, reason=PointsReason.FIRST_CHECKIN).count() == 1
        )
        assert (
            PointsTransaction.objects.filter(user=b, reason=PointsReason.FIRST_CHECKIN).count() == 1
        )


@pytest.mark.django_db
class TestIdempotencyOfPoints:
    def test_no_duplicate_tx_on_retry_pattern(self) -> None:
        """
        Сценарий: каким-то образом вызвали award вторично для того же
        checkin. Idempotency-constraint не даёт создать вторую транзакцию.
        """
        from apps.gamification.services import PointsService

        user = UserFactory()
        place = _make_place()
        checkin = CheckInService.create(
            user=user, place_id=place.pk, latitude=PLACE_LAT, longitude=PLACE_LNG
        )

        result = PointsService.award(
            user=user,
            reason=PointsReason.CHECKIN,
            ref_type="checkin",
            ref_id=checkin.pk,
        )
        assert result is None
        assert (
            PointsTransaction.objects.filter(
                user=user, reason=PointsReason.CHECKIN, ref_id=checkin.pk
            ).count()
            == 1
        )
