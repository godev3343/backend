"""
Построение queryset'ов для places-эндпоинтов.

Решения:
- primary_vibe считается на стороне БД через Subquery (ORDER BY weight DESC LIMIT 1),
  не Python-постфильтрацией. Это один запрос на список вместо N+1.
- thumb_asset_id — аналогично, Subquery latest по photos.created_at,
  затем .filter(asset__status=PROCESSED). url берётся в сериализаторе.
- Мульти-vibe фильтр — OR (`vibes__tag__in=...`) + .distinct(). UX-обоснование:
  карта с фильтром "calm OR romantic" должна показывать всё, что подходит
  хотя бы под один из выбранных вайбов.
"""

from __future__ import annotations

from django.db.models import BooleanField, ExpressionWrapper, OuterRef, Q, QuerySet, Subquery

from apps.places.filters import PlaceListQuery
from apps.places.models import Place, PlacePhoto, PlaceVibe


def build_list_queryset(query: PlaceListQuery) -> QuerySet[Place]:
    """
    Queryset для GET /api/places — компактные данные для маркеров карты.

    Аннотации:
        primary_vibe_tag — slug вайба с max weight, либо None если вайбов нет.
        thumb_asset_id — id MediaAsset последней фото места (только PROCESSED).
        _has_photo / _has_vibe — boolean'ы для сортировки (Q() в order_by
            запрещён в Django 5; через ExpressionWrapper получаем выражение,
            у которого есть .asc()/.desc()).

    NB: возвращаем именно queryset, чтобы view мог применить .values() / срез.
    """
    # Primary vibe — самый "сильный" тег этого места.
    primary_vibe_subquery = (
        PlaceVibe.objects.filter(place=OuterRef("pk"))
        .order_by("-weight", "tag")  # tag для детерминизма при равных весах
        .values("tag")[:1]
    )

    # Latest фото с готовым (processed) ассетом — для thumb на карте.
    # PROCESSED-проверка важна: пока картинка обрабатывается, key_feed/thumb
    # пустые, и MediaAsset.url_thumb упадёт в url_original (тот может быть HEIC).
    latest_photo_asset_subquery = (
        PlacePhoto.objects.filter(
            place=OuterRef("pk"),
            asset__status="processed",
        )
        .order_by("-created_at", "-id")
        .values("asset_id")[:1]
    )

    qs = (
        Place.objects.filter(
            location__bboverlaps=query.bbox,
            is_verified=True,  # на карте показываем только верифицированные
        )
        .select_related("category")
        .annotate(
            primary_vibe_tag=Subquery(primary_vibe_subquery),
            thumb_asset_id=Subquery(latest_photo_asset_subquery),
            _has_photo=ExpressionWrapper(
                Q(thumb_asset_id__isnull=False),
                output_field=BooleanField(),
            ),
            _has_vibe=ExpressionWrapper(
                Q(primary_vibe_tag__isnull=False),
                output_field=BooleanField(),
            ),
        )
    )

    if query.vibes:
        qs = qs.filter(vibes__tag__in=query.vibes).distinct()

    if query.category:
        qs = qs.filter(category__slug=query.category)

    # Сортировка: маркеры с фото и вайбом — выше, чтобы они визуально
    # выделялись среди пустых пинов; стабильный tiebreak по id.
    # True > False в Postgres, поэтому desc для "сначала те, у кого есть".
    qs = qs.order_by("-_has_photo", "-_has_vibe", "id")

    return qs[: query.limit]


def build_detail_queryset() -> QuerySet[Place]:
    """
    Queryset для GET /api/places/{id} — карточка с полной инфой.

    Используется как `.get(pk=...)` поверх. prefetch на вайбы и фото —
    в самом view, потому что recent_checkins требует доступа к request.user
    (нет, не требует — но это место для будущих фильтров приватности).
    """
    return Place.objects.select_related("category")
