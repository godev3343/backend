"""
Redis-токены для email verification и password reset.

Контракт:
- Email verify: 6-значный код, TTL 15 мин, ключ email_verify:{email}.
- Password reset: 32-байт base64-токен, TTL 1 час, ключ pwd_reset:{token}.

Атомарное чтение+удаление через GETDEL (Redis 6.2+).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from django.core.cache import cache
from django_redis import get_redis_connection  # type: ignore[import-untyped]

EMAIL_VERIFY_TTL_SEC = 15 * 60
PASSWORD_RESET_TTL_SEC = 60 * 60

EMAIL_VERIFY_KEY_PREFIX = "email_verify:"
PASSWORD_RESET_KEY_PREFIX = "pwd_reset:"


# ---------- Email verification ---------------------------------------------


@dataclass(frozen=True)
class EmailVerifyCode:
    email: str
    code: str


def _redis():
    """
    Возвращает raw-Redis-клиент (для GETDEL). django.core.cache не
    проксирует команды Redis 6.2+, поэтому идём напрямую.

    Если django-redis не подключён — используем низкоуровневое API
    из default-cache (но GETDEL там не будет, fallback на GET+DELETE).
    """
    try:
        return get_redis_connection("default")
    except Exception:
        return None


def generate_email_verify_code(email: str) -> EmailVerifyCode:
    """
    Создаёт 6-значный код, перезаписывает существующий (rate-limit отдельно).
    """
    code = f"{secrets.randbelow(1_000_000):06d}"
    key = f"{EMAIL_VERIFY_KEY_PREFIX}{email.lower()}"
    cache.set(key, code, timeout=EMAIL_VERIFY_TTL_SEC)
    return EmailVerifyCode(email=email, code=code)


def consume_email_verify_code(email: str, code: str) -> bool:
    """
    Атомарно проверяет код и удаляет его. True если совпало.

    Использует GETDEL (Redis 6.2+) — иначе race condition: между GET
    и DELETE другой запрос мог бы прочитать тот же код.
    """
    key = f"{EMAIL_VERIFY_KEY_PREFIX}{email.lower()}"
    raw = _redis()

    if raw is None:
        # Fallback — небезопасный, но рабочий для dev/test без django-redis
        stored = cache.get(key)
        if stored is None:
            return False
        cache.delete(key)
        return _constant_time_eq(str(stored), code)

    value = raw.execute_command("GETDEL", key)
    if value is None:
        return False
    stored = value.decode() if isinstance(value, bytes) else str(value)
    return _constant_time_eq(stored, code)


# ---------- Password reset --------------------------------------------------


def generate_password_reset_token(user_id: int) -> str:
    """
    Создаёт URL-safe токен 32 байта, кладёт user_id в Redis на 1 час.
    """
    token = secrets.token_urlsafe(32)
    key = f"{PASSWORD_RESET_KEY_PREFIX}{token}"
    cache.set(key, str(user_id), timeout=PASSWORD_RESET_TTL_SEC)
    return token


def consume_password_reset_token(token: str) -> int | None:
    """
    Атомарно возвращает user_id и удаляет токен. None если невалидный.
    """
    key = f"{PASSWORD_RESET_KEY_PREFIX}{token}"
    raw = _redis()

    if raw is None:
        stored = cache.get(key)
        if stored is None:
            return None
        cache.delete(key)
        try:
            return int(stored)
        except (TypeError, ValueError):
            return None

    value = raw.execute_command("GETDEL", key)
    if value is None:
        return None
    try:
        return int(value.decode() if isinstance(value, bytes) else value)
    except (TypeError, ValueError):
        return None


# ---------- helpers --------------------------------------------------------


def _constant_time_eq(a: str, b: str) -> bool:
    """secrets.compare_digest, но безопасно для unicode-входа."""
    return secrets.compare_digest(a.encode(), b.encode())
