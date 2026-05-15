"""
AchievementService — выдача ачивок пользователю.

Вызывается из других сервисов после доменных действий:
- CheckInService.create → trigger="checkin"
- ReviewService.create → trigger="review_posted"
- FriendshipService.accept_request → trigger="friendship_accepted"
- LikeService.like → trigger="like_received" (вызываем для автора чек-ина,
  не для лайкера — лайк получает контент-мейкер)

Идемпотентность: повторный check тех же ачивок для того же юзера = no-op
благодаря UniqueConstraint(user, achievement).
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.db import IntegrityError, transaction

from apps.gamification.achievements.checkers import CHECKERS, TRIGGERS
from apps.gamification.models import Achievement, UserAchievement

if TYPE_CHECKING:
    from apps.users.models import User

logger = logging.getLogger(__name__)


class AchievementService:
    """Все методы classmethod — сервис stateless."""

    @classmethod
    def check_for_user(
        cls,
        *,
        user: "User",
        trigger: str,
    ) -> list[Achievement]:
        """
        Проверить и выдать ачивки, привязанные к триггеру.

        Returns:
            Список свеже-выданных Achievement. Пустой, если ничего не дали
            (юзер не дотянул или уже получил).

        НЕ бросает исключения — это побочный эффект основного действия
        (чек-ина, отзыва), и его падение не должно ломать основной флоу.
        Все ошибки логируются.
        """
        codes_to_check = TRIGGERS.get(trigger, ())
        if not codes_to_check:
            return []

        # Уже полученные коды — отсекаем заранее, чтобы не дёргать чекеры.
        already_unlocked: set[str] = set(
            UserAchievement.objects.filter(
                user=user,
                achievement__code__in=codes_to_check,
            ).values_list("achievement__code", flat=True)
        )

        newly_unlocked: list[Achievement] = []
        for code in codes_to_check:
            if code in already_unlocked:
                continue

            checker = CHECKERS.get(code)
            if checker is None:
                logger.warning(
                    "achievement_no_checker", extra={"code": code}
                )
                continue

            try:
                if not checker(user):
                    continue
            except Exception:  # noqa: BLE001
                logger.exception(
                    "achievement_checker_failed",
                    extra={"code": code, "user_id": user.pk},
                )
                continue

            achievement = cls._unlock(user=user, code=code)
            if achievement is not None:
                newly_unlocked.append(achievement)

        return newly_unlocked

    @classmethod
    def _unlock(cls, *, user, code):
        try:
            achievement = Achievement.objects.get(code=code)
        except Achievement.DoesNotExist:
            logger.warning("achievement_not_in_db", extra={"code": code})
            return None

        # savepoint — гасит IntegrityError без подрыва внешней транзакции
        sid = transaction.savepoint()
        try:
            UserAchievement.objects.create(user=user, achievement=achievement)
            transaction.savepoint_commit(sid)
        except IntegrityError:
            transaction.savepoint_rollback(sid)
            return None

        logger.info("achievement_unlocked", extra={"code": code, "user_id": user.pk})
        return achievement