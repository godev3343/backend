# apps/core/openapi.py
import sys
from typing import Any

URL_PREFIX_TO_TAG: dict[str, str] = {
    # Auth — всё под /api/auth/
    "/api/auth/": "auth",

    # Users — профиль, онбординг
    "/api/users/me/points": "gamification",  # этот раньше, чтобы матчился до /api/users/
    "/api/users/me/preferences": "social",  # preferences живёт в social app
    "/api/users/": "users",

    # Social — друзья, поиск
    "/api/friends/": "social",
    "/api/friends": "social",  # без / на конце — для коллекций

    # Media — загрузка
    "/api/upload/": "media",
    "/api/media/": "media",

    # Places
    "/api/places/": "places",

    # Geocoding
    "/api/geocode/": "geocoding",

    # Checkins + лента
    "/api/checkins/": "checkins",
    "/api/feed/": "checkins",

    # Events
    "/api/events/": "events",

    # AI
    "/api/ai/": "ai",

    # System
    "/api/schema/": "system",
    "/health/": "system",
    "/ready/": "system",
}

# Дефолтные теги от spectacular — первый сегмент пути после /api/
DEFAULT_TAGS_TO_OVERRIDE = {
    "api", "health", "ready",
    "users", "social", "media", "places", "geocode", "geocoding",
    "checkins", "events", "ai", "gamification", "auth",
    "friends", "upload", "feed", "schema",
}


def assign_tag_by_path(result: dict[str, Any], generator: Any, request: Any, public: bool) -> dict[str, Any]:
    """
    Postprocessing hook: проставляет tags каждой операции по URL prefix.
    Перетирает дефолтные теги от spectacular, но сохраняет явно заданные через @extend_schema.
    """
    with open("/tmp/hook_called.txt", "a") as f:
        f.write(f"called, paths={len(result.get('paths', {}))}\n")
    paths = result.get("paths", {})
    for path, methods in paths.items():
        tag = _resolve_tag(path)
        if tag is None:
            continue

        for method, operation in methods.items():
            if method not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue

            existing_tags = operation.get("tags", [])
            # Перетираем если: тегов нет, ИЛИ все теги — дефолтные (из URL)
            if not existing_tags or all(t in DEFAULT_TAGS_TO_OVERRIDE for t in existing_tags):
                operation["tags"] = [tag]

    return result


def _resolve_tag(path: str) -> str | None:
    # Сортируем по длине префикса убывая — чтобы /api/users/me/points матчился раньше /api/users/
    for prefix in sorted(URL_PREFIX_TO_TAG, key=len, reverse=True):
        if path.startswith(prefix):
            return URL_PREFIX_TO_TAG[prefix]
    return None