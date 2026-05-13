from django.apps import AppConfig


class MediaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.media"
    label = "media_app"

    def ready(self) -> None:
        # Регистрация сигналов
        from apps.media import signals  # noqa: F401