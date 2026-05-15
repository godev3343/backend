from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"

    def ready(self) -> None:
        from django.conf import settings
        from rest_framework.settings import api_settings
        api_settings.reload()

        # Spectacular settings ломаются из-за бага в наследовании от APISettings:
        # после reload() property user_settings берёт REST_FRAMEWORK, а не SPECTACULAR_SETTINGS.
        # Принудительно ставим правильный _user_settings.
        from drf_spectacular.settings import spectacular_settings
        spectacular_settings._user_settings = getattr(settings, "SPECTACULAR_SETTINGS", {})
        # Сбросить кэш чтобы при следующем обращении атрибуты пересчитались из user_settings
        for attr in list(spectacular_settings._cached_attrs):
            delattr(spectacular_settings, attr)
        spectacular_settings._cached_attrs.clear()