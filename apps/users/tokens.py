"""
Redis-токены для email verification и password reset.

Контракт:
- Email verify: 6-значный код, TTL 15 мин, ключ email_verify:{email}.
- Password reset: 32-байт base64-токен, TTL 1 час, ключ pwd_reset:{token}.

Атомарное чтение+удаление через GETDEL (Redis 6.2+).

ВАЖНО про ключи и сериализацию:
- Пишем через `cache.set()` — django-redis добавляет KEY_PREFIX/VERSION
  (по умолчанию ":1:") к ключу и pickle'ит значение.
- Читаем через raw `GETDEL` — мы сами должны воспроизвести то же преобразование
  ключа (через `make_key`) и распиковать значение (через `pickle.loads`).
- Иначе ключ не находится (ищем "email_verify:x", а в Redis ":1:email_verify:x")
  и/или значение приходит в виде сырых pickle-байт.
"""

from __future__ import annotations

import hmac
import pickle
import secrets
from dataclasses import dataclass

from django.core.cache import cache, caches
from django_redis import get_redis_connection  # type: ignore[import-untyped]

EMAIL_VERIFY_TTL_SEC = 15 * 60
PASSWORD_RESET_TTL_SEC = 60 * 60

EMAIL_VERIFY_KEY_PREFIX = "email_verify:"
PASSWORD_RESET_KEY_PREFIX = "pwd_reset:"


# ---------- helpers --------------------------------------------------------


def _redis():
    """
    Возвращает raw-Redis-клиент (для GETDEL). django.core.cache не
    проксирует команды Redis 6.2+, поэтому идём напрямую.

    Если django-redis не подключён (например, в тестах с locmem) — None,
    тогда используется fallback на cache.get/cache.delete.
    """
    try:
        return get_redis_connection("default")
    except Exception:
        return None


def _make_real_key(logical_key: str) -> str:
    """
    Превращает логический ключ в реальный Redis-ключ — с тем же префиксом
    и версией, что добавляет django-redis при cache.set().

    "email_verify:x@y.com" -> ":1:email_verify:x@y.com"
    """
    return caches["default"].make_key(logical_key)


def _decode_cached_value(raw_value: bytes | str | None) -> str | None:
    """
    Распиковывает значение, прочитанное через raw GETDEL.

    django-redis пиклит значения при cache.set(), поэтому raw-чтение
    возвращает pickle-байты, а не строку. cache.get() делал бы это сам.
    """
    if raw_value is None:
        return None
    if isinstance(raw_value, str):
        raw_value = raw_value.encode()
    try:
        return str(pickle.loads(raw_value))  # noqa: S301 — доверенный источник, свой Redis
    except (pickle.UnpicklingError, EOFError, AttributeError, ValueError):
        # На случай если кто-то когда-то положил сырую строку (например, в тестах)
        return raw_value.decode(errors="replace")


def _constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


# ---------- Email verification ---------------------------------------------


@dataclass(frozen=True)
class EmailVerifyCode:
    email: str
    code: str


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
    logical_key = f"{EMAIL_VERIFY_KEY_PREFIX}{email.lower()}"
    raw = _redis()

    if raw is None:
        # Fallback для тестов на locmem: cache.get/delete сами разбираются
        # с префиксом и pickle.
        stored = cache.get(logical_key)
        if stored is None:
            return False
        cache.delete(logical_key)
        return _constant_time_eq(str(stored), code)

    real_key = _make_real_key(logical_key)
    value = raw.execute_command("GETDEL", real_key)
    stored = _decode_cached_value(value)
    if stored is None:
        return False
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
    logical_key = f"{PASSWORD_RESET_KEY_PREFIX}{token}"
    raw = _redis()

    if raw is None:
        stored = cache.get(logical_key)
        if stored is None:
            return None
        cache.delete(logical_key)
        try:
            return int(stored)
        except (TypeError, ValueError):
            return None

    real_key = _make_real_key(logical_key)
    value = raw.execute_command("GETDEL", real_key)
    stored = _decode_cached_value(value)
    if stored is None:
        return None
    try:
        return int(stored)
    except (TypeError, ValueError):
        return None