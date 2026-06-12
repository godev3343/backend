"""
GET /api/events — афиша.

Permissions: AllowAny (см. docs/PROJECT_DECISIONS.md, EPIC 7).
Создание/редактирование — только через Django Admin.
"""

from __future__ import annotations

from rest_framework.generics import ListAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny

from apps.events.filters import parse_list_query
from apps.events.serializers import EventListItemSerializer
from apps.events.services.query import build_list_queryset

from drf_spectacular.utils import OpenApiParameter, extend_schema


@extend_schema(
    tags=["events"],
    summary="Афиша событий",
    description=(
        "Список событий афиши. Доступен всем (AllowAny). Можно фильтровать по "
        "диапазону дат (`from`/`to`) и видимой области карты (`bbox`). "
        "Пагинация limit/offset."
    ),
    parameters=[
        OpenApiParameter(
            name="from",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Нижняя граница по времени начала (ISO 8601).",
        ),
        OpenApiParameter(
            name="to",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Верхняя граница по времени начала (ISO 8601).",
        ),
        OpenApiParameter(
            name="bbox",
            type=str,
            location=OpenApiParameter.QUERY,
            required=False,
            description="Границы области: `lng_min,lat_min,lng_max,lat_max`.",
        ),
    ],
)
class EventListView(ListAPIView):
    """
    GET /api/events?from=...&to=...&bbox=...&limit=50&offset=0
    """

    permission_classes = (AllowAny,)
    pagination_class = LimitOffsetPagination
    serializer_class = EventListItemSerializer

    def get_queryset(self):
        query = parse_list_query(
            from_raw=self.request.query_params.get("from"),
            to_raw=self.request.query_params.get("to"),
            bbox_raw=self.request.query_params.get("bbox"),
            limit_raw=self.request.query_params.get("limit"),
        )
        # сохраняем limit для paginate_queryset
        self._page_limit = query.limit
        return build_list_queryset(from_=query.from_, to=query.to, bbox=query.bbox)

    def paginate_queryset(self, queryset):
        paginator = self.paginator
        paginator.default_limit = getattr(self, "_page_limit", paginator.default_limit)
        return paginator.paginate_queryset(queryset, self.request, view=self)