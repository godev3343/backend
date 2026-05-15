"""
Тесты AchievementService.

Покрытие:
- Чекер срабатывает → ачивка выдаётся
- Чекер не срабатывает → ачивки нет
- Повторный check для уже-полученной — no-op
- Сломанный чекер (исключение) — не валит флоу, другие ачивки проверяются
- Триггер без чекеров (неизвестный) → []
- Code в реестре, но Achievement не в БД → лог + None
"""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib.gis.geos import Point

from apps.checkins.tests.factories import CheckInFactory
from apps.gamification.models import Achievement, UserAchievement
from apps.gamification.services.achievements import AchievementService
from apps.places.tests.factories import PlaceFactory
from apps.users.tests.factories import UserFactory


@pytest.fixture
def seeded_achievements(db) -> None:  # type: ignore[no-untyped-def]
    """Создаёт все Achievement из реестра."""
    Achievement.objects.bulk_create(
        [
            Achievement(code="pioneer", name_ru="Первооткрыватель",
                        description_ru="...", order=10),
            Achievement(code="critic", name_ru="Критик",
                        description_ru="...", order=20),
            Achievement(code="night_watch", name_ru="Ночной",
                        description_ru="...", order=30),
            Achievement(code="social_butterfly", name_ru="Душа",
                        description_ru="...", order=40),
            Achievement(code="paparazzi", name_ru="Папарацци",
                        description_ru="...", order=50),
        ]
    )


@pytest.mark.django_db
class TestPioneer:
    def test_unlocks_at_5_distinct_places(
        self, seeded_achievements
    ) -> None:
        user = UserFactory()
        for _ in range(5):
            place = PlaceFactory()
            CheckInFactory(
                user=user,
                place=place,
                location=Point(71.4, 51.1, srid=4326),
            )

        new = AchievementService.check_for_user(user=user, trigger="checkin")

        assert len(new) == 1
        assert new[0].code == "pioneer"
        assert UserAchievement.objects.filter(
            user=user, achievement__code="pioneer"
        ).exists()

    def test_not_unlocked_with_4_places(
        self, seeded_achievements
    ) -> None:
        user = UserFactory()
        for _ in range(4):
            place = PlaceFactory()
            CheckInFactory(
                user=user,
                place=place,
                location=Point(71.4, 51.1, srid=4326),
            )

        new = AchievementService.check_for_user(user=user, trigger="checkin")

        codes = [a.code for a in new]
        assert "pioneer" not in codes

    def test_duplicate_checkins_in_same_place_dont_count(
        self, seeded_achievements
    ) -> None:
        user = UserFactory()
        place = PlaceFactory()
        for _ in range(5):
            CheckInFactory(
                user=user,
                place=place,
                location=Point(71.4, 51.1, srid=4326),
            )

        new = AchievementService.check_for_user(user=user, trigger="checkin")

        codes = [a.code for a in new]
        assert "pioneer" not in codes


@pytest.mark.django_db
class TestIdempotency:
    def test_second_check_is_noop(self, seeded_achievements) -> None:
        user = UserFactory()
        for _ in range(5):
            CheckInFactory(
                user=user,
                place=PlaceFactory(),
                location=Point(71.4, 51.1, srid=4326),
            )

        first = AchievementService.check_for_user(user=user, trigger="checkin")
        second = AchievementService.check_for_user(user=user, trigger="checkin")

        assert len(first) == 1
        assert second == []
        assert UserAchievement.objects.filter(
            user=user, achievement__code="pioneer"
        ).count() == 1


@pytest.mark.django_db
class TestErrorIsolation:
    def test_broken_checker_does_not_break_others(
        self, seeded_achievements
    ) -> None:
        """Если один чекер кидает исключение, остальные всё равно проверяются."""
        user = UserFactory()
        for _ in range(5):
            CheckInFactory(
                user=user,
                place=PlaceFactory(),
                location=Point(71.4, 51.1, srid=4326),
            )

        with patch(
            "apps.gamification.achievements.checkers.is_night_watch",
            side_effect=RuntimeError("boom"),
        ):
            new = AchievementService.check_for_user(
                user=user, trigger="checkin"
            )

        codes = [a.code for a in new]
        # pioneer проверился и сработал, night_watch упал — игнор
        assert "pioneer" in codes


@pytest.mark.django_db
class TestUnknownCode:
    def test_code_in_registry_but_not_in_db(self) -> None:
        # Не вызываем seeded_achievements fixture — БД пустая.
        user = UserFactory()
        for _ in range(5):
            CheckInFactory(
                user=user,
                place=PlaceFactory(),
                location=Point(71.4, 51.1, srid=4326),
            )

        new = AchievementService.check_for_user(user=user, trigger="checkin")

        # Чекер сработал, но Achievement.objects.get(code='pioneer') кинул
        # DoesNotExist → сервис логирует и возвращает None
        assert new == []
        assert UserAchievement.objects.count() == 0


@pytest.mark.django_db
class TestUnknownTrigger:
    def test_no_checkers_for_trigger(self, seeded_achievements) -> None:
        user = UserFactory()
        new = AchievementService.check_for_user(
            user=user, trigger="unknown_trigger"
        )
        assert new == []