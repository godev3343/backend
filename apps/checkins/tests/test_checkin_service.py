# apps/checkins/tests/test_checkin_service.py
"""
Тесты бизнес-логики CheckInService.

Покрытие по ТЗ 6.5:
- чек-ин дальше 100м → TooFarFromPlace
- чек-ин в пределах → создан + +5 поинтов
- второй чек-ин в это же место не даёт first_checkin бонус (нет друзей)
- сценарий с другом: первый = бонус, повторный другом = без бонуса
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
from apps.social.models import FriendshipStatus
from apps.social.tests.factories import FriendshipFactory
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
        # Сам юзер в той же точке — 0м.
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
        # ~1 градус по широте = ~111км. Запредельно далеко.
        with pytest.raises(TooFarFromPlace):
            CheckInService.create(
                user=user,
                place_id=place.pk,
                latitude=PLACE_LAT + 1.0,
                longitude=PLACE_LNG,
            )
        assert CheckIn.objects.count() == 0

    def test_just_outside_100m_fails(self) -> None:
        """
        ~150м к северу от точки места.
        0.00135° по широте ≈ 150м. За пределами 100м → должен упасть.
        """
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
            latitude=PLACE_LAT + 0.00045,  # ~50м
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
                latitude=95.0,  # вне [-90, 90]
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
    def test_awards_checkin_points(self) -> None:
        user = UserFactory()
        place = _make_place()
        CheckInService.create(
            user=user, place_id=place.pk, latitude=PLACE_LAT, longitude=PLACE_LNG
        )
        # +5 за чек-ин
        # Друзей нет — first_checkin не начисляется.
        txs = list(
            PointsTransaction.objects.filter(user=user).order_by("created_at")
        )
        assert len(txs) == 1
        assert txs[0].reason == PointsReason.CHECKIN
        assert txs[0].delta == 5
        user.refresh_from_db()
        assert user.points == 5

    def test_no_first_checkin_bonus_when_no_friends(self) -> None:
        """Юзер без друзей чек-инится первый раз — бонуса нет (нет друзей)."""
        user = UserFactory()
        place = _make_place()
        CheckInService.create(
            user=user, place_id=place.pk, latitude=PLACE_LAT, longitude=PLACE_LNG
        )
        first_bonus = PointsTransaction.objects.filter(
            user=user, reason=PointsReason.FIRST_CHECKIN
        )
        assert not first_bonus.exists()

    def test_first_checkin_among_friends_awards_bonus(self) -> None:
        """
        a и b друзья. b чек-инится первым из своей friend-сети → +10.
        """
        a = UserFactory()
        b = UserFactory()
        FriendshipFactory(
            from_user=a, to_user=b, status=FriendshipStatus.ACCEPTED
        )
        place = _make_place()

        CheckInService.create(
            user=b, place_id=place.pk, latitude=PLACE_LAT, longitude=PLACE_LNG
        )

        bonus = PointsTransaction.objects.filter(
            user=b, reason=PointsReason.FIRST_CHECKIN
        )
        assert bonus.count() == 1
        assert bonus.first().delta == 10
        b.refresh_from_db()
        assert b.points == 5 + 10  # checkin + first_checkin

    def test_second_friend_does_not_get_first_bonus(self) -> None:
        """
        a уже чек-инилcя в место X. b — друг a — чек-инится туда же.
        b НЕ получает first_checkin (потому что друг уже там был).
        """
        a = UserFactory()
        b = UserFactory()
        FriendshipFactory(
            from_user=a, to_user=b, status=FriendshipStatus.ACCEPTED
        )
        place = _make_place()

        # a первый
        CheckInService.create(
            user=a, place_id=place.pk, latitude=PLACE_LAT, longitude=PLACE_LNG
        )
        # b второй (но первый из своих)
        CheckInService.create(
            user=b, place_id=place.pk, latitude=PLACE_LAT, longitude=PLACE_LNG
        )

        # У a friend_checkin был бы только если кто-то из его друзей был тут до него.
        # b — друг — пришёл ПОСЛЕ a. Значит a получил бонус (он первый из своих),
        # а b — НЕТ (a — его друг — уже отметился).
        a_bonus = PointsTransaction.objects.filter(
            user=a, reason=PointsReason.FIRST_CHECKIN
        ).exists()
        b_bonus = PointsTransaction.objects.filter(
            user=b, reason=PointsReason.FIRST_CHECKIN
        ).exists()
        assert a_bonus is True
        assert b_bonus is False

    def test_same_user_second_checkin_no_first_bonus(self) -> None:
        """
        Тот же юзер чек-инится дважды в одно место → бонус FIRST_CHECKIN
        только за первый раз. Семантика: бонус за разведку, не за повторы.
        """
        a = UserFactory()
        b = UserFactory()
        FriendshipFactory(
            from_user=a, to_user=b, status=FriendshipStatus.ACCEPTED
        )
        place = _make_place()

        CheckInService.create(
            user=b, place_id=place.pk, latitude=PLACE_LAT, longitude=PLACE_LNG
        )
        CheckInService.create(
            user=b, place_id=place.pk, latitude=PLACE_LAT, longitude=PLACE_LNG
        )

        first_bonuses = PointsTransaction.objects.filter(
            user=b, reason=PointsReason.FIRST_CHECKIN
        )
        assert first_bonuses.count() == 1


@pytest.mark.django_db
class TestIdempotencyOfPoints:
    def test_no_duplicate_tx_on_retry_pattern(self) -> None:
        """
        Сценарий: каким-то образом вызвали award вторично для того же
        checkin. Idempotency-constraint не даёт создать вторую транзакцию.
        Тестим напрямую через PointsService, чтобы было понятно что именно
        работает.
        """
        from apps.gamification.services import PointsService

        user = UserFactory()
        place = _make_place()
        checkin = CheckInService.create(
            user=user, place_id=place.pk, latitude=PLACE_LAT, longitude=PLACE_LNG
        )

        # Повторное награждение — должно вернуть None и не упасть
        result = PointsService.award(
            user=user,
            reason=PointsReason.CHECKIN,
            ref_type="checkin",
            ref_id=checkin.pk,
        )
        assert result is None
        # Транзакция всё ещё одна
        assert (
            PointsTransaction.objects.filter(
                user=user, reason=PointsReason.CHECKIN, ref_id=checkin.pk
            ).count()
            == 1
        )