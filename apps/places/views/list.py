"""
GET /api/places — список заведений в bbox для карты.

Permissions: AllowAny.
Обоснование: карта — первое что видит юзер до регистрации (см. ТЗ 2.2.4).
Чтобы онбординг не превращался в "сначала зарегайся — потом смотри",
читать карту разрешено всем. На запись (POST/PATCH) этого эндпоинта нет —
добавление и редактирование мест идёт через админку.

Кэш: 60с, версионируемый (см. apps/places/services/cache.py).
"""

from __future__ import annotations

from typing import Any

from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.media.models import MediaAsset
from apps.places.filters import parse_list_query
from apps.places.serializers import PlaceListItemSerializer
from apps.places.services.cache import (
    build_list_cache_key,
    get_cached_list,
    set_cached_list,
)
from apps.places.services.query import build_list_queryset


class PlaceListView(GenericAPIView):
    """
    GET /api/places?bbox=lng_min,lat_min,lng_max,lat_max&vibe=calm,active&category=cafe&limit=200

    bbox обязателен. vibe/category/limit опциональны.
    Возвращает максимум 500 мест (см. filters.MAX_LIMIT).
    """

    permission_classes = (AllowAny,)
    pagination_class = None  # маркеры карты — без пагинации, отдаём всё в bbox

    def get(self, request: Request) -> Response:
        query = parse_list_query(
            bbox_raw=request.query_params.get("bbox"),
            vibe_raw=request.query_params.get("vibe"),
            category_raw=request.query_params.get("category"),
            limit_raw=request.query_params.get("limit"),
        )

        cache_key = build_list_cache_key(query)
        cached = get_cached_list(cache_key)
        if cached is not None:
            return Response(cached)

        places = list(build_list_queryset(query))

        # Догружаем thumb-ассеты одним запросом: queryset аннотирует только
        # asset_id, а сериализатору нужны URL'ы — без этой подгрузки на каждую
        # строку был бы отдельный hit в БД (или None, если делать иначе).
        thumb_ids = [p.thumb_asset_id for p in places if p.thumb_asset_id]
        thumb_assets_map: dict[int, MediaAsset] = (
            {a.id: a for a in MediaAsset.objects.filter(id__in=thumb_ids)} if thumb_ids else {}
        )

        serializer = PlaceListItemSerializer(
            places,
            many=True,
            context={"thumb_assets_by_id": thumb_assets_map},
        )
        payload: list[dict[str, Any]] = serializer.data

        set_cached_list(cache_key, payload)
        return Response(payload)
