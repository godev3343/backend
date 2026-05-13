"""Type helpers для views, где IsAuthenticated гарантирует User."""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from rest_framework.request import Request

    from apps.users.models import User


def authed_user(request: Request) -> User:
    """
    Returns request.user as User.

    Use ТОЛЬКО в views с permission_classes = [IsAuthenticated, ...].
    Без permission — упадёт в рантайме на AnonymousUser.
    """
    return cast("User", request.user)