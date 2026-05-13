"""Throttle-классы для auth-эндпоинтов."""

from __future__ import annotations

from rest_framework.throttling import AnonRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = "auth_login"


class RegisterRateThrottle(AnonRateThrottle):
    scope = "auth_register"


class EmailVerifyRequestThrottle(AnonRateThrottle):
    """
    Ключ — email из тела запроса (если есть), иначе IP.
    Это защищает от перебора по конкретному email и одновременно
    от «опрыскивания» (spray) по IP.
    """

    scope = "email_verify_request"

    def get_cache_key(self, request, view):  # type: ignore[override, no-untyped-def]
        ident = request.data.get("email") if hasattr(request, "data") else None
        if not ident:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class PasswordResetRequestThrottle(AnonRateThrottle):
    scope = "password_reset_request"

    def get_cache_key(self, request, view):  # type: ignore[override, no-untyped-def]
        ident = request.data.get("email") if hasattr(request, "data") else None
        if not ident:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class GoogleAuthRateThrottle(AnonRateThrottle):
    scope = "google_auth"
