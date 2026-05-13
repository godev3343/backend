"""
Фасад над Mapbox-клиентом с Redis-кэшем.

Кэшируем по нормализованному ключу: lowercased + stripped query + locale.
TTL 24ч — адреса меняются редко, экономит квоту Mapbox.

NB: НЕ кэшируем proximity-bias. Запрос "Кафе" из Астаны и из Алматы
семантически разные, но для нашего use-case (поиск адреса для добавления
места админом) этого хватает. Если позже нужен proximity-aware кэш —
добавим в ключ.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from typing import Any

from django.core.cache import cache

from apps.geocoding.services.exceptions import InvalidGeocodingQuery
from apps.geocoding.services.mapbox import GeocodeResult, forward_geocode

GEOCODE_CACHE_TTL = 24 * 60 * 60  # 24h
MIN_QUERY_LEN = 2
MAX_QUERY_LEN = 200


def geocode(
    query: str,
    *,
    proximity: tuple[float, float] | None = None,
    limit: int = 5,
    language: str = "ru",
    country: str = "kz",
) -> list[GeocodeResult]:
    """
    Возвращает кандидатов из Mapbox с кэшированием.
    Бросает InvalidGeocodingQuery / GeocodingUpstreamError / GeocodingNotConfigured.
    """
    normalized = _normalize_query(query)
    if not normalized:
        raise InvalidGeocodingQuery()

    cache_key = _build_cache_key(normalized, limit, language, country)
    cached = cache.get(cache_key)
    if cached is not None:
        return [GeocodeResult(**item) for item in cached]

    results = forward_geocode(
        normalized,
        proximity=proximity,
        limit=limit,
        language=language,
        country=country,
    )

    # Сериализуем dataclass'ы в dict для кэша — Redis не умеет хранить dataclass'ы
    # через стандартный pickle-протокол кэша без regressions, dict надёжнее.
    serializable: list[dict[str, Any]] = [asdict(r) for r in results]
    cache.set(cache_key, serializable, timeout=GEOCODE_CACHE_TTL)
    return results


def _normalize_query(raw: str | None) -> str:
    if not raw:
        return ""
    s = " ".join(raw.split()).strip().lower()
    if len(s) < MIN_QUERY_LEN or len(s) > MAX_QUERY_LEN:
        return ""
    return s


def _build_cache_key(query: str, limit: int, language: str, country: str) -> str:
    # Хэш — потому что в query могут быть символы, неудобные для Redis-ключа
    # (пробелы, двоеточия, кавычки). md5 здесь не для безопасности, только
    # для генерации компактного детерминированного ключа.
    digest = hashlib.md5(query.encode("utf-8")).hexdigest()
    return f"geocode:v1:{language}:{country}:{limit}:{digest}"
