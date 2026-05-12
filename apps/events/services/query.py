# apps/events/services/query.py
"""
Построение queryset'ов для events-эндпоинтов.

Решения:
- "Событие активно в окне [from, to)" = starts_at < to AND
  (ends_at > from OR (ends_at IS NULL AND starts_at >= from)).
  Это включает одноразовые ивенты в будущем (нет ends_at, но starts_at в окне),
  длящиеся (ends_at где-то после from), и исключает закончившиеся.
- bbox-фильтр работает на event.location (денормализован из place.location
  в Event.save и в миграции 0003). Один индекс, никаких JOIN'ов.
"""
from __future__ import annotations

from datetime import datetime

from django.contrib.gis.geos import Polygon
from django.db.models import Q, QuerySet

from apps.events.models import Event


def build_list_queryset(
    *,
    from_: datetime,
    to: datetime,
    bbox: Polygon | None,
) -> QuerySet[Event]:
    """
    Queryset для афиши. select_related('place') — потому что сериализатор
    list-элемента кладёт {id, name} места. Без него N+1 на каждый ивент.
    """
    qs = (
        Event.objects.select_related("place")
        .filter(starts_at__lt=to)
        .filter(
            Q(ends_at__gt=from_)
            | Q(ends_at__isnull=True, starts_at__gte=from_)
        )
        .order_by("starts_at", "id")
    )

    if bbox is not None:
        qs = qs.filter(location__bboverlaps=bbox)

    return qs


def build_detail_queryset() -> QuerySet[Event]:
    """Queryset для GET /api/events/{id}. Используется как `.get(pk=...)` поверх."""
    return Event.objects.select_related("place", "place__category")