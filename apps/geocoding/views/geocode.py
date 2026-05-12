"""
GET /api/geocode?q=...&proximity=lng,lat&limit=5

Permissions: IsAuthenticated.
Обоснование: геокодинг проксирует платный (free-tier) API Mapbox. Открыть
его анонимам — приглашение к сжиганию квоты. Авторизованные юзеры дополнительно
зарезаны throttle scope.

Throttle: scope 'geocode' = 60/h на пользователя (см. settings).
"""
from __future__ import annotations

from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from apps.geocoding.serializers import GeocodeResultSerializer
from apps.geocoding.services.exceptions import InvalidGeocodingQuery
from apps.geocoding.services.geocoder import geocode


class GeocodeThrottle(UserRateThrottle):
    scope = "geocode"


def _parse_proximity(raw: str | None) -> tuple[float, float] | None:
    if not raw:
        return None
    parts = raw.split(",")
    if len(parts) != 2:
        return None
    try:
        lng, lat = float(parts[0]), float(parts[1])
    except ValueError:
        return None
    if not (-180.0 <= lng <= 180.0) or not (-90.0 <= lat <= 90.0):
        return None
    return (lng, lat)


def _parse_limit(raw: str | None, default: int = 5, max_value: int = 10) -> int:
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value < 1:
        return default
    return min(value, max_value)


class GeocodeView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (GeocodeThrottle,)
    serializer_class = GeocodeResultSerializer

    def get(self, request: Request) -> Response:
        query = request.query_params.get("q", "").strip()
        if not query:
            raise InvalidGeocodingQuery()

        proximity = _parse_proximity(request.query_params.get("proximity"))
        limit = _parse_limit(request.query_params.get("limit"))
        language = request.query_params.get("language", "ru")
        country = request.query_params.get("country", "kz")

        results = geocode(
            query,
            proximity=proximity,
            limit=limit,
            language=language,
            country=country,
        )
        serializer = self.serializer_class(results, many=True)
        return Response({"results": serializer.data})