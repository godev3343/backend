"""
Кэш для списка мест.

Стратегия — версионирование, не delete_pattern:
- В Redis живёт счётчик `places:version` (int).
- Ключ кэша списка содержит текущую версию: `places:list:v{N}:...`.
- Любое изменение Place / PlaceVibe инкрементит версию (см. signals.py).
- Старые ключи с предыдущей версией становятся мусором и протухают по TTL.

Почему не delete_pattern: встроенный Django RedisCache (Django 4.0+) его
не поддерживает — это метод django-redis. Версионирование решает задачу
без новой зависимости и работает за O(1) на инвалидацию.
"""
from __future__ import annotations

from typing import Any

from django.core.cache import cache

from apps.places.filters import PlaceListQuery

# TTL списка маркеров. 60с — компромисс между свежестью (новое место /
# смена вайба видны "почти сразу") и эффективностью кэша при панорамировании.
PLACE_LIST_CACHE_TTL = 60

# Счётчик существует вечно (без TTL). При первом обращении создаём = 1.
VERSION_KEY = "places:version"
# Кэшируем сам счётчик в локальной памяти процесса — версия меняется редко,
# незачем дёргать Redis на каждый list-запрос.
# Тем не менее тесты могут менять версию мимо `bump_version()`,
# поэтому это soft-cache: при miss идём в Redis.


def get_version() -> int:
    """
    Возвращает текущую версию инвалидации. Если ключ ещё не создан —
    создаёт его как 1 (атомарно через add).
    """
    version = cache.get(VERSION_KEY)
    if version is None:
        # add() — set-if-not-exists, защищает от гонки между несколькими воркерами
        cache.add(VERSION_KEY, 1, timeout=None)
        version = cache.get(VERSION_KEY) or 1
    return int(version)


def bump_version() -> int:
    """
    Инкрементирует версию. Вызывается сигналами на save/delete Place/PlaceVibe.
    Возвращает новое значение (для тестов и логов).
    """
    try:
        return int(cache.incr(VERSION_KEY))
    except ValueError:
        # Ключа не существовало — создаём и возвращаем 1.
        # Это не "сбрасывает кэш в 1" в проде, потому что get_version()
        # уже создал бы его при первом list-запросе. Тут защита от cold start
        # на тестах и сценария "Redis был очищен flushall".
        cache.set(VERSION_KEY, 1, timeout=None)
        return 1


def build_list_cache_key(query: PlaceListQuery) -> str:
    """
    Детерминированный ключ кэша для list-запроса.

    Версия включена в ключ — bump_version() автоматически инвалидирует
    весь набор без явного удаления.
    """
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
    return cache.get(key)


def set_cached_list(key: str, payload: list[dict[str, Any]]) -> None:
    cache.set(key, payload, timeout=PLACE_LIST_CACHE_TTL)