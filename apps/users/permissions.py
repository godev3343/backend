"""Кастомные permissions для auth-флоу."""

from __future__ import annotations

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsEmailVerified(BasePermission):
    """
    Требует подтверждённого email. Применять к действиям,
    требующим доверия: чек-ины, посты, заявки в друзья.

    Не блокирует логин / просмотр карты / редактирование профиля.
    """

    message = "Email is not verified."
    code = "email_not_verified"

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "is_email_verified", False))


class IsOnboarded(BasePermission):
    """Требует пройденного онбординга: consent_at + display_name."""

    message = "Onboarding is not completed."
    code = "onboarding_required"

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and getattr(user, "is_onboarded", False))
