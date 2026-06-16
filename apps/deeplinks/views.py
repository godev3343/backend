"""
Публичные view для deep linking (Android App Links + landing шаринга).

Все три отдаются в КОРНЕ домена (не под /api/), без авторизации — это
требование Android-верификации и превью-ботов мессенджеров. well-known файлы
сознательно отдаём через Django-view, а не как статику: так гарантируем
Content-Type и отсутствие редиректов (guide §2.4).
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.deeplinks.services import build_preview

logger = logging.getLogger(__name__)

# Android-верификация и AASA редко меняются — час кэша снимает лишние запросы.
_WELL_KNOWN_CACHE = "public, max-age=3600"
# Landing-превью может поменяться (правка поста) — короткий кэш для ботов.
_LANDING_CACHE = "public, max-age=300"


@require_GET
def assetlinks(request: HttpRequest) -> HttpResponse:
    """
    GET /.well-known/assetlinks.json — верификация Android App Links.

    Если package/fingerprints не заданы в env — отдаём 404 и пишем warning,
    чтобы проблема была видна в логах, а не молча ломала autoVerify пустым
    массивом (guide §2.2 A).
    """
    package = settings.ANDROID_PACKAGE_NAME
    fingerprints = settings.ANDROID_CERT_FINGERPRINTS
    if not package or not fingerprints:
        logger.warning(
            "assetlinks.json requested but ANDROID_PACKAGE_NAME/"
            "ANDROID_CERT_FINGERPRINTS are not configured"
        )
        raise Http404("assetlinks not configured")

    payload = [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": package,
                "sha256_cert_fingerprints": fingerprints,
            },
        }
    ]
    response = JsonResponse(payload, safe=False)
    response["Cache-Control"] = _WELL_KNOWN_CACHE
    return response


@require_GET
def apple_app_site_association(request: HttpRequest) -> HttpResponse:
    """
    GET /.well-known/apple-app-site-association — ЗАГЛУШКА под iOS.

    Сейчас отдаём пустую валидную конфигурацию: URL должен существовать и
    возвращать application/json без расширения в пути. Когда появится Apple
    Developer аккаунт — заполнить details:
        {"appID": "TEAMID.com.go.app.go_app",
         "paths": ["/posts/*", "/users/*", "/checkins/*", "/places/*", "/events/*"]}
    (guide §2.2 B, §9).
    """
    payload = {"applinks": {"details": []}}
    response = JsonResponse(payload)
    response["Cache-Control"] = _WELL_KNOWN_CACHE
    return response


@require_GET
def landing(request: HttpRequest, entity: str, entity_id: str) -> HttpResponse:
    """
    GET /{entity}/{id} — fallback HTML для тех, у кого приложение не стоит.

    Если приложение установлено, Android перехватит ссылку до рендера. Сюда
    доезжает только «безприложный» трафик и превью-боты — отдаём OG-карточку и
    уводим в Play Store.
    """
    preview = build_preview(entity, entity_id)

    # og:url / canonical — абсолютная шаринг-ссылка. В проде берём из
    # DEEPLINK_DOMAIN; в dev (домен пуст) — из самого запроса.
    if settings.DEEPLINK_DOMAIN:
        canonical_url = f"https://{settings.DEEPLINK_DOMAIN}/{entity}/{entity_id}"
    else:
        canonical_url = request.build_absolute_uri()

    response = render(
        request,
        "deeplinks/landing.html",
        {
            "preview": preview,
            "canonical_url": canonical_url,
            "play_store_url": settings.PLAY_STORE_URL,
        },
    )
    response["Cache-Control"] = _LANDING_CACHE
    return response
