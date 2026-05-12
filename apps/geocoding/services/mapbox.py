"""
Тонкая обёртка над Mapbox Geocoding API v6.

Мы используем endpoint `forward` (текст → координаты). Не нормализуем
ответ агрессивно — отдаём фронту максимально близкий к Mapbox shape,
чтобы при миграции на Photon (этап 2) можно было решить структуру отдельно.

Только базовые поля, не "all features":
- id (mapbox feature id)
- name (place_name из Mapbox)
- lat, lng
- place_type (например, address, poi, region)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from django.conf import settings

from apps.geocoding.services.exceptions import (
    GeocodingNotConfigured,
    GeocodingUpstreamError,
)

logger = structlog.get_logger(__name__)

MAPBOX_FORWARD_URL = "https://api.mapbox.com/search/geocode/v6/forward"
MAPBOX_TIMEOUT_SEC = 5.0
MAPBOX_MAX_RESULTS = 10


@dataclass(frozen=True, slots=True)
class GeocodeResult:
    id: str
    name: str
    lat: float
    lng: float
    place_type: str


def forward_geocode(
    query: str,
    *,
    proximity: tuple[float, float] | None = None,
    limit: int = 5,
    language: str = "ru",
    country: str = "kz",
) -> list[GeocodeResult]:
    """
    Текст → список кандидатов с координатами.

    proximity — (lng, lat) для приоритизации результатов рядом с точкой.
        Mapbox использует это для буста, не для жёсткого фильтра.
    country — ISO 3166-1 alpha-2; ограничиваем выдачу страной по умолчанию
        (Казахстан). На уровне API можно переопределить.
    """
    token = getattr(settings, "MAPBOX_ACCESS_TOKEN", "")
    if not token:
        raise GeocodingNotConfigured()

    params: dict[str, Any] = {
        "q": query,
        "access_token": token,
        "limit": min(max(limit, 1), MAPBOX_MAX_RESULTS),
        "language": language,
        "country": country,
    }
    if proximity is not None:
        params["proximity"] = f"{proximity[0]},{proximity[1]}"

    try:
        response = httpx.get(
            MAPBOX_FORWARD_URL,
            params=params,
            timeout=MAPBOX_TIMEOUT_SEC,
        )
    except httpx.HTTPError as e:
        logger.warning("mapbox_request_failed", error=str(e), query=query)
        raise GeocodingUpstreamError() from e

    if response.status_code >= 500:
        logger.warning(
            "mapbox_5xx",
            status=response.status_code,
            query=query,
        )
        raise GeocodingUpstreamError()
    if response.status_code >= 400:
        # 4xx обычно — невалидный токен или request-level баг.
        # Лог + наружу 502, чтобы клиент не получил детали внутренней
        # конфигурации.
        logger.error(
            "mapbox_4xx",
            status=response.status_code,
            body=response.text[:500],
            query=query,
        )
        raise GeocodingUpstreamError()

    try:
        data = response.json()
    except ValueError as e:
        logger.warning("mapbox_invalid_json", query=query)
        raise GeocodingUpstreamError() from e

    return _parse_features(data.get("features", []))


def _parse_features(features: list[dict[str, Any]]) -> list[GeocodeResult]:
    """
    Mapbox v6 формат feature:
    {
      "id": "...",
      "geometry": {"type": "Point", "coordinates": [lng, lat]},
      "properties": {
        "name": "...",
        "full_address": "...",
        "feature_type": "address" | "place" | "poi" | ...
      }
    }
    """
    out: list[GeocodeResult] = []
    for f in features:
        try:
            coords = f["geometry"]["coordinates"]
            props = f.get("properties", {})
            out.append(
                GeocodeResult(
                    id=str(f.get("id", "")),
                    # full_address полнее чем name, лучше для display
                    name=props.get("full_address") or props.get("name") or "",
                    lng=float(coords[0]),
                    lat=float(coords[1]),
                    place_type=props.get("feature_type", ""),
                )
            )
        except (KeyError, IndexError, TypeError, ValueError):
            # Битый feature — пропускаем, не валим весь ответ
            continue
    return out