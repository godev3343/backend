"""Throttle scopes для social-эндпоинтов."""
from __future__ import annotations

from rest_framework.throttling import UserRateThrottle


class FriendRequestThrottle(UserRateThrottle):
    """Создание friend request. Анти-спам."""

    scope = "friend_request"


class UserSearchThrottle(UserRateThrottle):
    """Поиск юзеров. Анти-скрейпинг."""

    scope = "user_search"