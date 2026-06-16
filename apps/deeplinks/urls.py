"""
Маршруты deep linking — в КОРНЕ домена (подключаются в config/urls.py с
пустым префиксом, не под /api/).

- well-known файлы: точные пути без trailing slash (Android/Apple дёргают
  ровно эти имена).
- landing: re_path, ограниченный 5 сущностями — чтобы не перехватывать чужие
  корневые пути (admin/, api/ и т.п.) и не плодить дженерик-страницу на любой
  двухсегментный URL. Слеш на конце опционален (`/?`), чтобы APPEND_SLASH не
  делал 301 на путях, которые открывает приложение.
"""

from __future__ import annotations

from django.urls import path, re_path

from apps.deeplinks import views
from apps.deeplinks.services import SUPPORTED_ENTITIES

app_name = "deeplinks"

_entities = "|".join(sorted(SUPPORTED_ENTITIES))

urlpatterns = [
    path(".well-known/assetlinks.json", views.assetlinks, name="assetlinks"),
    path(
        ".well-known/apple-app-site-association",
        views.apple_app_site_association,
        name="aasa",
    ),
    re_path(
        rf"^(?P<entity>{_entities})/(?P<entity_id>[^/]+)/?$",
        views.landing,
        name="landing",
    ),
]
