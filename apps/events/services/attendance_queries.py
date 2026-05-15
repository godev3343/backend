"""
Запросы для attendance, переиспользуемые между endpoint'ом /attendance
и расширением EventDetailSerializer.

Решение: queryset-функции, а не методы AttendanceService — они read-only
и не имеют побочных эффектов. Сервис только для записи.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.events.models import EventAttendance
from apps.social.models import Friendship, FriendshipStatus


def friend_ids_subquery(user_id: int):
    """
    Subquery с pk друзей юзера (ACCEPTED в любом направлении).

    Возвращает не values, а готовый QuerySet для использования в __in.
    Postgres скомпилирует в EXISTS/JOIN корректно.
    """
    sent = Friendship.objects.filter(
        from_user_id=user_id,
        status=FriendshipStatus.ACCEPTED,
    ).values_list("to_user_id", flat=True)

    received = Friendship.objects.filter(
        to_user_id=user_id,
        status=FriendshipStatus.ACCEPTED,
    ).values_list("from_user_id", flat=True)

    # values_list по двум разным querysets — нельзя сделать UNION в __in
    # напрямую через Django ORM без union(). Простой вариант: материализуем
    # в Python. На pre-MVP до сотен друзей у одного юзера — ок.
    # Когда упрёмся (1k+ друзей) — заменим на UNION/EXISTS subquery.
    return list(set(sent).union(received))


def friends_attending_qs(
        *,
        viewer_id: int,
        event_id: int,
) -> QuerySet[EventAttendance]:
    """
    Attendance записи друзей viewer'а на event.
    Отсортированы по убыванию created_at — последние записавшиеся сверху.

    select_related('user__avatar_asset') нужен для FriendAttendanceSerializer,
    который кладёт avatar_url (через User.avatar_url → MediaAsset.url_feed).
    """
    friend_ids = friend_ids_subquery(viewer_id)
    if not friend_ids:
        return EventAttendance.objects.none()

    return (
        EventAttendance.objects
        .filter(event_id=event_id, user_id__in=friend_ids)
        .select_related("user", "user__avatar_asset")
        .order_by("-created_at", "-id")
    )