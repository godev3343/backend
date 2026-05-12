"""
PointsService — единая точка начисления поинтов.

Архитектура:
- award() — атомарная операция: создаёт PointsTransaction + инкрементит User.points.
- Идемпотентность через UniqueConstraint на (user, reason, ref_type, ref_id).
  Повторный вызов с тем же ref → IntegrityError → ловим и возвращаем None.
- POINTS_BY_REASON — единый источник правды по размеру награды. Не хардкодим
  числа в вызывающих сервисах: CheckInService просит "начисли за CHECKIN",
  а сколько именно — решает gamification.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import IntegrityError, transaction
from django.db.models import F

from apps.gamification.models import PointsReason, PointsTransaction

if TYPE_CHECKING:
    from apps.users.models import User


# Размер награды по причине. Источник правды — здесь, не в вызывающем коде.
POINTS_BY_REASON: dict[str, int] = {
    PointsReason.SIGNUP: 10,
    PointsReason.CHECKIN: 5,
    PointsReason.FIRST_CHECKIN: 10,
    PointsReason.REFERRAL: 20,
}


class PointsService:
    """Stateless — все методы classmethod."""

    @classmethod
    def award(
        cls,
        *,
        user: "User",
        reason: str,
        ref_type: str = "",
        ref_id: int | None = None,
    ) -> PointsTransaction | None:
        """
        Начисляет поинты пользователю.

        Идемпотентно: повторный вызов с тем же (user, reason, ref_type, ref_id)
        возвращает None и НЕ начисляет дважды. Реальный размер берётся из
        POINTS_BY_REASON.

        Контракт:
            ref_id=None → одноразовое начисление (как SIGNUP). Уникальность
                          по (user, reason).
            ref_id=N    → событийное (CHECKIN на checkin#42). Уникальность
                          по (user, reason, ref_type, ref_id).

        Использовать внутри @transaction.atomic из вызывающего сервиса,
        чтобы создание чек-ина и поинтов либо коммитились вместе, либо
        откатывались вместе. Сам метод тоже оборачивает в savepoint
        для корректного обработки IntegrityError при идемпотентности.

        Returns:
            PointsTransaction — если начисление произошло.
            None — если транзакция с таким ref уже существует (idempotent no-op).
        """
        if reason not in POINTS_BY_REASON:
            raise ValueError(f"Unknown points reason: {reason!r}")

        delta = POINTS_BY_REASON[reason]

        # Savepoint — чтобы IntegrityError на дубликате не уронил внешнюю
        # транзакцию (CheckInService остаётся валидным).
        try:
            with transaction.atomic():
                tx = PointsTransaction.objects.create(
                    user=user,
                    delta=delta,
                    reason=reason,
                    ref_type=ref_type,
                    ref_id=ref_id,
                )
                # F-выражение — атомарное увеличение на стороне БД.
                # Не делаем user.points += delta, чтобы не было гонок
                # между параллельными чек-инами одного юзера.
                type(user).objects.filter(pk=user.pk).update(
                    points=F("points") + delta
                )
                # Локальный объект может быть stale — синхронизируем
                # для удобства вызывающего кода.
                user.points = (user.points or 0) + delta
        except IntegrityError:
            # Дубликат по UniqueConstraint — поинты уже начислены, всё ок.
            return None

        return tx