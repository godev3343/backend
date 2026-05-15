"""AttendanceService — управление "иду/не иду" на событиях."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from apps.events.models import Event, EventAttendance
from apps.events.services.exceptions import AttendanceEventNotFound

if TYPE_CHECKING:
    from apps.users.models import User as UserType


class AttendanceService:
    """Stateless — все методы classmethod, по аналогии с FriendshipService."""

    @classmethod
    @transaction.atomic
    def mark_going(cls, *, user: UserType, event_id: int) -> EventAttendance:
        """
        Юзер идёт на event. Идемпотентно: повторный вызов возвращает
        существующую запись.

        Бросает AttendanceEventNotFound если event не существует — иначе
        FK-уровневая ошибка протекла бы наружу.
        """
        # Проверяем существование явно — get_or_create на несуществующий
        # event_id даст IntegrityError, что неприятно ловить.
        if not Event.objects.filter(pk=event_id).exists():
            raise AttendanceEventNotFound()

        attendance, _ = EventAttendance.objects.get_or_create(
            event_id=event_id,
            user=user,
        )
        return attendance

    @classmethod
    @transaction.atomic
    def cancel(cls, *, user: UserType, event_id: int) -> bool:
        """
        Отменить участие. True если запись была и удалена, False если
        её не было. Не бросает исключения — повторный DELETE = idempotent.
        """
        deleted, _ = EventAttendance.objects.filter(
            event_id=event_id,
            user=user,
        ).delete()
        return deleted > 0

    @classmethod
    def is_going(cls, *, user_id: int, event_id: int) -> bool:
        """Идёт ли user на event."""
        return EventAttendance.objects.filter(
            event_id=event_id,
            user_id=user_id,
        ).exists()

    @classmethod
    def count_for_event(cls, event_id: int) -> int:
        """Сколько всего человек идёт на event."""
        return EventAttendance.objects.filter(event_id=event_id).count()