from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"


    def ready(self) -> None:
        # DRF's api_settings закешировался до полной загрузки settings.REST_FRAMEWORK
        # (drf_spectacular или рендереры дёрнули его рано). Форсируем перечитывание,
        # иначе DEFAULT_SCHEMA_CLASS и прочие наши overrides не подхватятся.
        from rest_framework.settings import api_settings
        api_settings.reload()
