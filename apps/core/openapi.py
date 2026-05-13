"""
drf-spectacular preprocessing hook: автоматически проставляет OpenAPI tag
по Django app_label view-класса, чтобы не обвешивать каждую view декоратором.

Маппинг прост:
  apps.users (path /api/auth/*)  → "auth"
  apps.users (всё остальное)     → "users"
  apps.<other>                    → "<other>"
  /health, /ready                 → "system"

Когда добавляется новый app — он автоматом получает тег по своему имени.
Если нужен другой тег для конкретной view — поставить @extend_schema(tags=[...]),
этот hook его не перетрёт.
"""

from __future__ import annotations

from typing import Any

# Apps, для которых имя app != имя тега. Сейчас один кейс — users разделяется
# на auth-эндпоинты (по path) и остальные. Можно расширять.
_SPECIAL_PATH_TAGS: dict[str, str] = {
    "/api/auth/": "auth",
}


def _tag_for(path: str, app_label: str | None) -> str:
    # Path-based override (для auth внутри apps.users)
    for prefix, tag in _SPECIAL_PATH_TAGS.items():
        if path.startswith(prefix):
            return tag

    # System endpoints без app
    if path.startswith("/health") or path.startswith("/ready"):
        return "system"
    if path.startswith("/api/schema") or path.startswith("/api/docs"):
        return "system"

    # Default: app_label или fallback
    return app_label or "system"


def assign_tag_by_app(
    endpoints: list[tuple[str, str, str, Any]],
    **kwargs: Any,
) -> list[tuple[str, str, str, Any]]:
    """
    Preprocessing hook drf-spectacular.

    На каждый endpoint смотрим app_label view-класса (через __module__).
    Уважаем @extend_schema(tags=[...]) — не перетираем явные теги.
    """
    for path, _path_regex, _method, callback in endpoints:
        view = getattr(callback, "cls", None)
        if view is None:
            continue
        if getattr(view, "_spectacular_autotag_done", False):
            continue

        # apps.users.views.register.RegisterView → "users"
        module = getattr(view, "__module__", "") or ""
        app_label: str | None = None
        if module.startswith("apps."):
            # apps.users.views.X → ["apps", "users", ...]
            app_label = module.split(".")[1]

        tag = _tag_for(path, app_label)
        view.tags = [tag]
        view._spectacular_autotag_done = True

    return endpoints
