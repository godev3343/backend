"""Хелперы для chat-тестов: онбордженные юзеры + взаимная дружба."""

from __future__ import annotations

from typing import Any

from django.utils.timezone import now

from apps.social.models import Friendship, FriendshipStatus
from apps.users.tests.factories import UserFactory


def onboarded_user(**kwargs: Any) -> Any:
    """Юзер, прошедший email-verify + онбординг (нужно для chat-permissions)."""
    defaults = {
        "email_verified_at": now(),
        "consent_at": now(),
        "display_name": kwargs.pop("display_name", None) or "user",
    }
    defaults.update(kwargs)
    return UserFactory(**defaults)


def make_friends(user_a: Any, user_b: Any) -> Friendship:
    """Подтверждённая дружба (ACCEPTED) между двумя юзерами."""
    return Friendship.objects.create(
        from_user=user_a, to_user=user_b, status=FriendshipStatus.ACCEPTED
    )
