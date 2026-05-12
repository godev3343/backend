"""
Парсинг и валидация query-параметров для list-эндпоинта.

Решение: НЕ используем django-filter здесь, потому что bbox и vibe требуют
специфической валидации (числа+порядок, choices+CSV), а в результате нам
нужен датакласс, а не Q-объект. django-filter добавил бы шум без выигрыша.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from django.contrib.gis.geos import Polygon

from apps.places.models import PlaceVibeTag
from apps.places.services.exceptions import (
    BBoxTooLarge,
    InvalidBBox,
    InvalidVibe,
)

# Максимальная диагональ bbox в градусах.
# 2° ≈ 220км по широте — два размера крупного города. Если больше, заставляем
# зумиться: иначе клиент дёрнет тысячи маркеров и положит запрос.
MAX_BBOX_SPAN_DEG = 2.0

# Лимиты для query-параметра limit. Default 200 — типовой viewport маркеров,
# max 500 — потолок, чтобы не выдавать всю Астану одним JSON'ом.
DEFAULT_LIMIT = 200
MAX_LIMIT = 500

VALID_VIBE_TAGS: frozenset[str] = frozenset(PlaceVibeTag.values)


@dataclass(frozen=True, slots=True)
class PlaceListQuery:
    """Уже распарсенные и валидированные параметры list-запроса."""

    bbox: Polygon
    # bbox в исходном виде "lng_min,lat_min,lng_max,lat_max" — для cache key.
    # Не пересчитываем из Polygon, потому что Polygon.extent даёт float'ы
    # которые после round-trip отличаются на ULP и ломают cache hit-rate.
    bbox_raw_rounded: str
    vibes: tuple[str, ...] = field(default_factory=tuple)
    category: str = ""
    limit: int = DEFAULT_LIMIT


def parse_list_query(
    bbox_raw: str | None,
    vibe_raw: str | None,
    category_raw: str | None,
    limit_raw: str | None,
) -> PlaceListQuery:
    """
    Превращает сырые query-параметры в PlaceListQuery или бросает PlacesError.
    """
    if not bbox_raw:
        raise InvalidBBox("Missing 'bbox' query parameter.")

    bbox = _parse_bbox(bbox_raw)
    bbox_raw_rounded = _round_bbox_key(bbox_raw)

    vibes = _parse_vibes(vibe_raw)
    category = (category_raw or "").strip()
    limit = _parse_limit(limit_raw)

    return PlaceListQuery(
        bbox=bbox,
        bbox_raw_rounded=bbox_raw_rounded,
        vibes=vibes,
        category=category,
        limit=limit,
    )


def _parse_bbox(raw: str) -> Polygon:
    parts = raw.split(",")
    if len(parts) != 4:
        raise InvalidBBox()
    try:
        lng_min, lat_min, lng_max, lat_max = (float(p) for p in parts)
    except ValueError as e:
        raise InvalidBBox() from e

    if not (-180.0 <= lng_min < lng_max <= 180.0):
        raise InvalidBBox()
    if not (-90.0 <= lat_min < lat_max <= 90.0):
        raise InvalidBBox()

    if (lng_max - lng_min) > MAX_BBOX_SPAN_DEG or (lat_max - lat_min) > MAX_BBOX_SPAN_DEG:
        raise BBoxTooLarge()

    return Polygon.from_bbox((lng_min, lat_min, lng_max, lat_max))


def _parse_vibes(raw: str | None) -> tuple[str, ...]:
    if not raw:
        return ()
    raw_tags = [t.strip() for t in raw.split(",") if t.strip()]
    invalid = [t for t in raw_tags if t not in VALID_VIBE_TAGS]
    if invalid:
        raise InvalidVibe(
            f"Unknown vibe(s): {', '.join(invalid)}. "
            f"Valid: {', '.join(sorted(VALID_VIBE_TAGS))}.",
        )
    # dedupe + стабильный порядок для cache key
    return tuple(sorted(set(raw_tags)))


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


def _round_bbox_key(raw: str) -> str:
    """
    Округляем bbox до 3 знаков после запятой (~110м на экваторе).
    Это нужно для cache hit-rate: при панорамировании карты на 10м клиент
    шлёт slightly different bbox; без округления каждый запрос — cache miss.
    """
    try:
        nums = [float(p) for p in raw.split(",")]
    except ValueError:
        return raw
    return ",".join(f"{n:.3f}" for n in nums)