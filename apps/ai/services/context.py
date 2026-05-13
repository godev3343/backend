"""
Сборка контекста для AI-промпта: топ-N мест города + ближайшие события.

Результат — текстовый блок, который кладётся в system prompt.
Кэшируется в Redis на 30 мин по ключу с версией вайбов (см. signals.py).

На pre-MVP — только Астана, фильтр по Place.city. На Этапе 1 — city
будет параметром.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

from apps.events.models import Event
from apps.places.models import City, Place, PlaceVibe

# Ограничения контекста — балансируем покрытие vs стоимость токенов.
# 50 мест × ~80 токенов = ~4K, 20 событий × ~50 токенов = ~1K. Влезает.
MAX_PLACES_IN_CONTEXT = 50
MAX_EVENTS_IN_CONTEXT = 20
EVENTS_WINDOW_DAYS = 7

# Кэш — 30 мин. Версия вайбов в ключе делает инвалидацию атомарной.
CONTEXT_CACHE_TTL_SECONDS = 30 * 60
VIBES_VERSION_KEY = "ai:vibes_version"


def get_vibes_version() -> int:
    """Текущая версия вайбов. Инкрементится в signals.py при изменении PlaceVibe."""
    version = cache.get(VIBES_VERSION_KEY)
    if version is None:
        cache.set(VIBES_VERSION_KEY, 1, timeout=None)
        return 1
    return int(version)


def bump_vibes_version() -> None:
    """Инвалидация AI-контекста после изменения вайбов."""
    try:
        cache.incr(VIBES_VERSION_KEY)
    except ValueError:
        # ключа нет — заводим
        cache.set(VIBES_VERSION_KEY, 1, timeout=None)


@dataclass(frozen=True)
class AiContext:
    """Готовый текстовый блок для system prompt + множество валидных place_id."""

    text: str
    valid_place_ids: frozenset[int]


def build_context(city: str = City.ASTANA.value) -> AiContext:
    """
    Собирает контекст города. Результат кэшируется на 30 мин в Redis.

    valid_place_ids возвращается отдельно — это белый список для фильтра
    hallucinated id'шников из ответа модели.
    """
    cache_key = f"ai:context:{city}:v{get_vibes_version()}"
    cached: dict | None = cache.get(cache_key)
    if cached is not None:
        return AiContext(
            text=cached["text"],
            valid_place_ids=frozenset(cached["valid_place_ids"]),
        )

    text, valid_ids = _build_uncached(city)
    cache.set(
        cache_key,
        {"text": text, "valid_place_ids": list(valid_ids)},
        timeout=CONTEXT_CACHE_TTL_SECONDS,
    )
    return AiContext(text=text, valid_place_ids=frozenset(valid_ids))


def _build_uncached(city: str) -> tuple[str, list[int]]:
    """Сборка без обращения к кэшу. Используется только из build_context."""
    places = _top_places(city)
    events = _upcoming_events(city)

    blocks: list[str] = ["# Заведения города"]
    valid_ids: list[int] = []
    for p in places:
        blocks.append(_format_place(p))
        valid_ids.append(p.id)

    if events:
        blocks.append("\n# Ближайшие события (7 дней)")
        for e in events:
            blocks.append(_format_event(e))

    return ("\n\n".join(blocks), valid_ids)


def _top_places(city: str) -> list[Place]:
    """
    Топ-N мест города. "Топ" = сумма весов вайбов (proxy для "интересность").
    Без вайбов места уходят в хвост, но не отсеиваются — модель может
    хотя бы по категории и описанию что-то порекомендовать.

    select_related('category') и prefetch вайбов одним запросом — иначе
    N+1 в _format_place.
    """
    from django.db.models import Prefetch

    return list(
        Place.objects.filter(city=city, is_verified=True)
        .annotate(vibes_weight_sum=Sum("vibes__weight"))
        .select_related("category")
        .prefetch_related(
            Prefetch(
                "vibes",
                queryset=PlaceVibe.objects.order_by("-weight"),
            )
        )
        .order_by("-vibes_weight_sum", "id")[:MAX_PLACES_IN_CONTEXT]
    )


def _upcoming_events(city: str) -> list[Event]:
    """
    События в ближайшие EVENTS_WINDOW_DAYS дней.

    Event.location денормализован, но фильтра по city у него нет.
    На pre-MVP в Астане один город — берём все события. На Этапе 1
    добавим Event.city или JOIN на Place.city.
    """
    now = timezone.now()
    horizon = now + timedelta(days=EVENTS_WINDOW_DAYS)
    return list(
        Event.objects.select_related("place")
        .filter(starts_at__lt=horizon)
        .filter(starts_at__gte=now)
        .order_by("starts_at", "id")[:MAX_EVENTS_IN_CONTEXT]
    )


def _format_place(p: Place) -> str:
    """
    Компактный текстовый блок для одного места. Формат стабильный — модель
    привыкает к структуре, экономим токены на повторных запросах.
    """
    vibes = list(p.vibes.all())
    vibes_str = ", ".join(f"{v.tag}({float(v.weight):.1f})" for v in vibes) if vibes else "—"

    lines = [
        f"[place_id={p.id}] {p.name}",
        f"  Категория: {p.category.name_ru}",
        f"  Вайб: {vibes_str}",
        f"  Адрес: {p.address}" if p.address else None,
        f"  Описание: {p.description}" if p.description else None,
    ]
    return "\n".join(line for line in lines if line)


def _format_event(e: Event) -> str:
    """Компактный блок для события."""
    when = e.starts_at.strftime("%Y-%m-%d %H:%M")
    venue = e.place.name if e.place else "по адресу"
    return f"[event_id={e.id}] {e.title} — {when}, {venue}\n  {(e.description or '')[:200]}"
