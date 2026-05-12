"""
LikeService — лайки на чек-ины.

Поведение API:
- POST /api/checkins/{id}/like:
    * первый раз — создаёт Like, инкрементит likes_count, возвращает 201.
    * повторно (уже лайкнул) — НЕ создаёт, возвращает 200. Идемпотентный
      tap на сердечко не должен бросать 409.
- DELETE /api/checkins/{id}/like:
    * лайк был — удаляем, декрементим, 204.
    * лайка не было — 204 (идемпотентность). Не 404, потому что для UI
      "у меня нет лайка" и "я попытался убрать лайк которого нет" — это
      одно и то же конечное состояние.

Счётчик `CheckIn.likes_count` — единственное место, которое сервис меняет
помимо строк Like. Обновляем через F-выражение, чтобы две параллельные
+1/-1 не затёрли друг друга.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import IntegrityError, transaction
from django.db.models import F

from apps.checkins.models import CheckIn, Like
from apps.checkins.services.exceptions import CheckInNotFound

if TYPE_CHECKING:
    from apps.users.models import User as UserType


class LikeResult:
    """Простой enum результата like(): для view — какой статус вернуть."""

    CREATED = "created"  # 201
    ALREADY_LIKED = "already_liked"  # 200
    REMOVED = "removed"  # 204
    WAS_NOT_LIKED = "was_not_liked"  # 204 — тоже ok-исход


class LikeService:
    """Stateless — все методы classmethod."""

    @classmethod
    @transaction.atomic
    def like(cls, *, user: "UserType", checkin_id: int) -> str:
        """
        Возвращает один из LikeResult.CREATED / ALREADY_LIKED.

        Raises:
            CheckInNotFound — если checkin_id не существует.
        """
        # Проверяем существование. select_for_update не нужен — мы не
        # обновляем CheckIn напрямую, только через F-выражение, которое
        # атомарно само по себе.
        if not CheckIn.objects.filter(pk=checkin_id).exists():
            raise CheckInNotFound()

        try:
            Like.objects.create(user=user, checkin_id=checkin_id)
        except IntegrityError:
            # UniqueConstraint(user, checkin) — дубль. Это нормальный
            # путь: юзер тапнул сердечко второй раз.
            return LikeResult.ALREADY_LIKED

        # Инкремент счётчика — F() избегает гонки на параллельных лайках.
        CheckIn.objects.filter(pk=checkin_id).update(
            likes_count=F("likes_count") + 1
        )
        return LikeResult.CREATED

    @classmethod
    @transaction.atomic
    def unlike(cls, *, user: "UserType", checkin_id: int) -> str:
        """
        Возвращает LikeResult.REMOVED / WAS_NOT_LIKED.

        Raises:
            CheckInNotFound — если checkin_id не существует.
        """
        if not CheckIn.objects.filter(pk=checkin_id).exists():
            raise CheckInNotFound()

        deleted_count, _ = Like.objects.filter(
            user=user, checkin_id=checkin_id
        ).delete()

        if deleted_count == 0:
            return LikeResult.WAS_NOT_LIKED

        # F() с защитой от ухода в отрицательное (модель PositiveIntegerField,
        # F('x') - 1 при x=0 уйдёт в -1 и упрётся в check_constraint).
        # На практике если deleted_count == 1, то Like существовал, а значит
        # счётчик был >= 1. Но защищаемся явно — Greatest(0, x-1).
        from django.db.models.functions import Greatest

        CheckIn.objects.filter(pk=checkin_id).update(
            likes_count=Greatest(F("likes_count") - 1, 0)
        )
        return LikeResult.REMOVED