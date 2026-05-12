"""
GET /api/events — афиша.

Permissions: AllowAny (см. docs/PROJECT_DECISIONS.md, EPIC 7).
Создание/редактирование — только через Django Admin.
"""
from __future__ import annotations

from rest_framework.generics import GenericAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.events.filters import parse_list_query
from apps.events.serializers import EventListItemSerializer
from apps.events.services.query import build_list_queryset


class EventListView(GenericAPIView):
    """
    GET /api/events?from=2026-05-12T00:00:00Z&to=2026-05-26T00:00:00Z
                   &bbox=lng_min,lat_min,lng_max,lat_max&limit=50&offset=0

    Все параметры опциональны.
    Default: from = now, to = now + 14 дней, без bbox.
    """

    permission_classes = (AllowAny,)
    pagination_class = LimitOffsetPagination
    serializer_class = EventListItemSerializer

    def get(self, request: Request) -> Response:
        query = parse_list_query(
            from_raw=request.query_params.get("from"),
            to_raw=request.query_params.get("to"),
            bbox_raw=request.query_params.get("bbox"),
            limit_raw=request.query_params.get("limit"),
        )

        qs = build_list_queryset(from_=query.from_, to=query.to, bbox=query.bbox)

        paginator = self.pagination_class()
        # query.limit уже прошёл cap до MAX_LIMIT в parse_list_query —
        # переопределяем default_limit пагинатора, чтобы дефолт совпал с нашим.
        paginator.default_limit = query.limit
        page = paginator.paginate_queryset(qs, request, view=self)

        serializer = self.serializer_class(page, many=True)
        return paginator.get_paginated_response(serializer.data)