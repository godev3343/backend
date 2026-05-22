"""
Кэш для списка мест.

Стратегия — версионирование, не delete_pattern (см. предыдущую версию).
Все операции best-effort: если Redis недоступен, возвращаем фоллбэк-значения
и логируем warning. Бизнес-логика (save/delete Place) НЕ должна ронять запрос
из-за лежащего Redis.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.cache import cache

from apps.places.filters import PlaceListQuery

logger = logging.getLogger(__name__)

PLACE_LIST_CACHE_TTL = 60
VERSION_KEY = "places:version"


def get_version() -> int:
    """
    Текущая версия инвалидации. При недоступности Redis или отсутствии ключа
    возвращает 1 (фоллбэк) — ключи кэша всё равно будут детерминированными.
    """
    try:
        version = cache.get(VERSION_KEY)
    except Exception:
        logger.warning("Redis unavailable on get_version", exc_info=True)
        return 1

    if version is None:
        try:
            cache.add(VERSION_KEY, 1, timeout=None)
            version = cache.get(VERSION_KEY)
        except Exception:
            logger.warning("Redis unavailable on get_version init", exc_info=True)
            return 1
        if version is None:
            return 1

    try:
        return int(version)
    except (TypeError, ValueError):
        return 1


def bump_version() -> int:
    """
    Инкрементит версию кэша. Возвращает новое значение.

    Устойчиво к:
    - отсутствию ключа (ValueError от incr) → создаём = 1
    - недоступности Redis (Exception или None от IGNORE_EXCEPTIONS) → возвращаем 0,
      бизнес-операция продолжается без инвалидации кэша
    """
    try:
        result = cache.incr(VERSION_KEY)
    except ValueError:
        # Ключа не было — создаём.
        try:
            cache.set(VERSION_KEY, 1, timeout=None)
            return 1
        except Exception:
            logger.warning("Redis unavailable on bump_version init", exc_info=True)
            return 0
    except Exception:
        logger.warning("Redis unavailable on bump_version", exc_info=True)
        return 0

    # IGNORE_EXCEPTIONS=True проглотит сетевую ошибку и вернёт None.
    if result is None:
        logger.warning("cache.incr returned None — Redis likely unavailable")
        return 0

    try:
        return int(result)
    except (TypeError, ValueError):
        return 0


def build_list_cache_key(query: PlaceListQuery) -> str:
    version = get_version()
    vibes_part = "+".join(query.vibes) if query.vibes else "-"
    category_part = query.category or "-"
    return (
        f"places:list:v{version}"
        f":bbox={query.bbox_raw_rounded}"
        f":vibes={vibes_part}"
        f":cat={category_part}"
        f":lim={query.limit}"
    )


def get_cached_list(key: str) -> list[dict[str, Any]] | None:
    try:
        return cache.get(key)
    except Exception:
        logger.warning("Redis unavailable on get_cached_list", exc_info=True)
        return None


def set_cached_list(key: str, payload: list[dict[str, Any]]) -> None:
    try:
        cache.set(key, payload, timeout=PLACE_LIST_CACHE_TTL)
    except Exception:
        logger.warning("Redis unavailable on set_cached_list", exc_info=True)