# apps/checkins/tests/test_like_service.py
"""Тесты LikeService: идемпотентность like/unlike и счётчик."""

from __future__ import annotations

import pytest

from apps.checkins.models import Like
from apps.checkins.services import LikeResult, LikeService
from apps.checkins.services.exceptions import CheckInNotFound
from apps.checkins.tests.factories import CheckInFactory
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestLike:
    def test_first_like_creates(self) -> None:
        user = UserFactory()
        checkin = CheckInFactory()
        result = LikeService.like(user=user, checkin_id=checkin.pk)
        assert result == LikeResult.CREATED
        assert Like.objects.filter(user=user, checkin=checkin).count() == 1
        checkin.refresh_from_db()
        assert checkin.likes_count == 1

    def test_second_like_idempotent(self) -> None:
        user = UserFactory()
        checkin = CheckInFactory()
        LikeService.like(user=user, checkin_id=checkin.pk)
        result = LikeService.like(user=user, checkin_id=checkin.pk)
        assert result == LikeResult.ALREADY_LIKED
        # Счётчик НЕ инкрементится повторно
        checkin.refresh_from_db()
        assert checkin.likes_count == 1
        assert Like.objects.count() == 1

    def test_two_different_users_both_like(self) -> None:
        a = UserFactory()
        b = UserFactory()
        checkin = CheckInFactory()
        LikeService.like(user=a, checkin_id=checkin.pk)
        LikeService.like(user=b, checkin_id=checkin.pk)
        checkin.refresh_from_db()
        assert checkin.likes_count == 2

    def test_checkin_not_found(self) -> None:
        user = UserFactory()
        with pytest.raises(CheckInNotFound):
            LikeService.like(user=user, checkin_id=999_999)


@pytest.mark.django_db
class TestUnlike:
    def test_unlike_existing(self) -> None:
        user = UserFactory()
        checkin = CheckInFactory()
        LikeService.like(user=user, checkin_id=checkin.pk)

        result = LikeService.unlike(user=user, checkin_id=checkin.pk)
        assert result == LikeResult.REMOVED
        checkin.refresh_from_db()
        assert checkin.likes_count == 0
        assert not Like.objects.filter(user=user, checkin=checkin).exists()

    def test_unlike_idempotent_when_no_like(self) -> None:
        user = UserFactory()
        checkin = CheckInFactory()
        result = LikeService.unlike(user=user, checkin_id=checkin.pk)
        assert result == LikeResult.WAS_NOT_LIKED
        # Счётчик не уезжает в минус
        checkin.refresh_from_db()
        assert checkin.likes_count == 0

    def test_counter_does_not_go_negative_on_corrupted_state(self) -> None:
        """
        Защита от рассинхронизации: если каким-то образом likes_count = 0,
        но Like-запись есть (или наоборот), повторный unlike не должен
        дать отрицательный счётчик.
        """
        user = UserFactory()
        checkin = CheckInFactory(likes_count=0)
        # Создаём Like напрямую, без сервиса (так инкремент не сработает)
        Like.objects.create(user=user, checkin=checkin)

        LikeService.unlike(user=user, checkin_id=checkin.pk)
        checkin.refresh_from_db()
        assert checkin.likes_count == 0  # не -1


@pytest.mark.django_db
class TestLikeFlow:
    def test_like_then_unlike_then_like_again(self) -> None:
        user = UserFactory()
        checkin = CheckInFactory()

        LikeService.like(user=user, checkin_id=checkin.pk)
        LikeService.unlike(user=user, checkin_id=checkin.pk)
        LikeService.like(user=user, checkin_id=checkin.pk)

        checkin.refresh_from_db()
        assert checkin.likes_count == 1
        assert Like.objects.filter(user=user, checkin=checkin).count() == 1
