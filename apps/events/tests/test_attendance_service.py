"""Тесты AttendanceService — бизнес-логика."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.gis.geos import Point
from django.utils.timezone import now

from apps.events.models import EventAttendance
from apps.events.services.attendance import AttendanceService
from apps.events.services.exceptions import AttendanceEventNotFound
from apps.events.tests.factories import EventFactory
from apps.users.tests.factories import UserFactory


@pytest.mark.django_db
class TestMarkGoing:
    def test_creates_attendance(self) -> None:
        user = UserFactory()
        event = EventFactory()
        a = AttendanceService.mark_going(user=user, event_id=event.pk)
        assert a.user_id == user.pk
        assert a.event_id == event.pk
        assert EventAttendance.objects.count() == 1

    def test_is_idempotent(self) -> None:
        """Двойной POST 'иду' — одна запись, без 409."""
        user = UserFactory()
        event = EventFactory()
        a1 = AttendanceService.mark_going(user=user, event_id=event.pk)
        a2 = AttendanceService.mark_going(user=user, event_id=event.pk)
        assert a1.pk == a2.pk
        assert EventAttendance.objects.count() == 1

    def test_event_not_found(self) -> None:
        user = UserFactory()
        with pytest.raises(AttendanceEventNotFound):
            AttendanceService.mark_going(user=user, event_id=999_999)

    def test_multiple_users_same_event(self) -> None:
        event = EventFactory()
        for _ in range(5):
            AttendanceService.mark_going(user=UserFactory(), event_id=event.pk)
        assert AttendanceService.count_for_event(event.pk) == 5


@pytest.mark.django_db
class TestCancel:
    def test_removes_attendance(self) -> None:
        user = UserFactory()
        event = EventFactory()
        AttendanceService.mark_going(user=user, event_id=event.pk)
        assert AttendanceService.cancel(user=user, event_id=event.pk) is True
        assert EventAttendance.objects.count() == 0

    def test_cancel_without_attendance(self) -> None:
        """Идемпотентно: cancel когда не идёшь — не падает, возвращает False."""
        user = UserFactory()
        event = EventFactory()
        assert AttendanceService.cancel(user=user, event_id=event.pk) is False


@pytest.mark.django_db
class TestQueries:
    def test_is_going(self) -> None:
        user = UserFactory()
        event = EventFactory()
        assert not AttendanceService.is_going(user_id=user.pk, event_id=event.pk)
        AttendanceService.mark_going(user=user, event_id=event.pk)
        assert AttendanceService.is_going(user_id=user.pk, event_id=event.pk)

    def test_count_only_for_specific_event(self) -> None:
        e1 = EventFactory()
        e2 = EventFactory()
        AttendanceService.mark_going(user=UserFactory(), event_id=e1.pk)
        AttendanceService.mark_going(user=UserFactory(), event_id=e1.pk)
        AttendanceService.mark_going(user=UserFactory(), event_id=e2.pk)
        assert AttendanceService.count_for_event(e1.pk) == 2
        assert AttendanceService.count_for_event(e2.pk) == 1