"""
Чекеры ачивок — функции, которые отвечают на вопрос
"заслужил ли юзер эту ачивку прямо сейчас?".

Каждый чекер — pure read-only функция от User → bool. Никаких сайд-эффектов:
выдачей ачивки занимается AchievementService поверх результата чекера.

Названия слагов в _CHECKERS должны совпадать с Achievement.code из fixture.
"""
from __future__ import annotations

from datetime import time
from typing import TYPE_CHECKING, Callable

from django.db import models
from django.db.models import Count, Q

if TYPE_CHECKING:
    from apps.users.models import User


def is_pioneer(user: "User") -> bool:
    """«Первооткрыватель» — чек-ины в 5+ разных мест."""
    from apps.checkins.models import CheckIn

    count = (
        CheckIn.objects.filter(user=user)
        .values("place_id")
        .distinct()
        .count()
    )
    return count >= 5


def is_night_watch(user: "User") -> bool:
    """«Ночной дозор» — 10+ чек-инов после 00:00 локального времени."""
    from apps.checkins.models import CheckIn

    # Простая семантика: смотрим по UTC. На pre-MVP юзеры в одной TZ (Астана),
    # сдвиг 5ч — после 00:00 локального = после 19:00 UTC.
    # На Этапе 1, если будет важно, перейдём на per-user timezone в модели.
    night_count = CheckIn.objects.filter(
        user=user,
        created_at__time__gte=time(19, 0),  # 19:00 UTC = 00:00 Astana
    ).count()
    # Это упрощение: ночь до 5 утра (10 UTC) тоже считается. На практике
    # реальные ночные чек-ины (00:00–05:00 local = 19:00–24:00 UTC) попадают.
    # Для pre-MVP достаточно.
    return night_count >= 10


def is_critic(user: "User") -> bool:
    """«Ресторанный критик» — 15+ отзывов с фото."""
    from apps.reviews.models import Review

    count = Review.objects.filter(user=user, photo__isnull=False).count()
    return count >= 15


def is_social_butterfly(user: "User") -> bool:
    """«Душа компании» — 5+ принятых заявок в друзья (в любую сторону)."""
    from django.db.models import Q

    from apps.social.models import Friendship, FriendshipStatus

    count = Friendship.objects.filter(
        Q(from_user=user) | Q(to_user=user),
        status=FriendshipStatus.ACCEPTED,
    ).count()
    return count >= 5


def is_paparazzi(user: "User") -> bool:
    """«Папарацци» — 50+ фото от юзера, собравших 100+ лайков суммарно.

    Считаем по PlacePhoto + CheckIn-фото юзера и суммируем likes_count
    с привязанных чек-инов. Аппроксимация — пока у нас лайки только на
    чек-инах, не на самих фото.
    """
    from apps.checkins.models import CheckIn

    photos_with_likes = (
        CheckIn.objects.filter(user=user, photo__isnull=False)
        .aggregate(
            photo_count=Count("id"),
            total_likes=models.Sum("likes_count"),
        )
    )
    photo_count = photos_with_likes["photo_count"] or 0
    total_likes = photos_with_likes["total_likes"] or 0
    return photo_count >= 50 and total_likes >= 100


# Registry: code → checker function.
# Code должен совпадать с Achievement.code из fixtures/achievements.json.
CHECKERS: dict[str, Callable[["User"], bool]] = {
    "pioneer": is_pioneer,
    "night_watch": is_night_watch,
    "critic": is_critic,
    "social_butterfly": is_social_butterfly,
    "paparazzi": is_paparazzi,
}


# Маппинг trigger → коды ачивок, которые нужно проверить при этом триггере.
# Это оптимизация: не проверяем все ачивки на каждый чек-ин.
TRIGGERS: dict[str, tuple[str, ...]] = {
    "checkin": ("pioneer", "night_watch", "paparazzi"),
    "review_posted": ("critic",),
    "friendship_accepted": ("social_butterfly",),
    "like_received": ("paparazzi",),
}