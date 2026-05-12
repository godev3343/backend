"""Доменные ошибки геокодинг-сервиса."""
from __future__ import annotations

from apps.core.exceptions import DomainError


class GeocodingError(DomainError):
    default_message = "Geocoding error."
    default_code = "geocoding_error"
    status_code = 502  # ошибка во внешнем апстриме


class InvalidGeocodingQuery(GeocodingError):
    default_message = "Invalid 'q' parameter."
    default_code = "invalid_query"
    status_code = 400


class GeocodingUpstreamError(GeocodingError):
    """Mapbox вернул не-2xx или таймаут."""

    default_message = "Geocoding provider is unavailable."
    default_code = "upstream_unavailable"
    status_code = 502


class GeocodingNotConfigured(GeocodingError):
    """MAPBOX_ACCESS_TOKEN не задан в env."""

    default_message = "Geocoding is not configured on the server."
    default_code = "not_configured"
    status_code = 503