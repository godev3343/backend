from __future__ import annotations

from django.apps import AppConfig


class PlacesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.places"
    label = "places"

    def ready(self) -> None:
        # Регистрируем сигналы инвалидации кэша.
        from apps.places import signals  # noqa: F401