"""
Парсинг и валидация query-параметров для GET /api/events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.contrib.gis.geos import Polygon
from django.utils.dateparse import parse_datetime
from django.utils.timezone import now

from apps.events.services.exceptions import (
    EventsBBoxTooLarge,
    EventsInvalidBBox,
    InvalidPeriod,
)

# Окно афиши по умолчанию.
DEFAULT_PERIOD_DAYS = 14

# Та же логика, что и в places: 2° по диагонали ≈ 220 км.
MAX_BBOX_SPAN_DEG = 2.0

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


@dataclass(frozen=True, slots=True)
class EventListQuery:
    from_: datetime
    to: datetime
    bbox: Polygon | None
    limit: int


def parse_list_query(
    from_raw: str | None,
    to_raw: str | None,
    bbox_raw: str | None,
    limit_raw: str | None,
) -> EventListQuery:
    """Превращает сырые query-параметры в EventListQuery или бросает доменную ошибку."""
    from_, to = _parse_period(from_raw, to_raw)
    bbox = _parse_bbox(bbox_raw) if bbox_raw else None
    limit = _parse_limit(limit_raw)
    return EventListQuery(from_=from_, to=to, bbox=bbox, limit=limit)


def _parse_period(from_raw: str | None, to_raw: str | None) -> tuple[datetime, datetime]:
    current = now()

    if from_raw:
        from_ = parse_datetime(from_raw)
        if from_ is None or from_.tzinfo is None:
            raise InvalidPeriod("'from' must be ISO-8601 datetime with timezone.")
    else:
        from_ = current

    if to_raw:
        to = parse_datetime(to_raw)
        if to is None or to.tzinfo is None:
            raise InvalidPeriod("'to' must be ISO-8601 datetime with timezone.")
    else:
        to = from_ + timedelta(days=DEFAULT_PERIOD_DAYS)

    if to <= from_:
        raise InvalidPeriod("'to' must be greater than 'from'.")

    return from_, to


def _parse_bbox(raw: str) -> Polygon:
    parts = raw.split(",")
    if len(parts) != 4:
        raise EventsInvalidBBox()
    try:
        lng_min, lat_min, lng_max, lat_max = (float(p) for p in parts)
    except ValueError as e:
        raise EventsInvalidBBox() from e

    if not (-180.0 <= lng_min < lng_max <= 180.0):
        raise EventsInvalidBBox()
    if not (-90.0 <= lat_min < lat_max <= 90.0):
        raise EventsInvalidBBox()

    if (lng_max - lng_min) > MAX_BBOX_SPAN_DEG or (lat_max - lat_min) > MAX_BBOX_SPAN_DEG:
        raise EventsBBoxTooLarge()

    return Polygon.from_bbox((lng_min, lat_min, lng_max, lat_max))


def _parse_limit(raw: str | None) -> int:
    if not raw:
        return DEFAULT_LIMIT
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_LIMIT
    if value < 1:
        return DEFAULT_LIMIT
    return min(value, MAX_LIMIT)
