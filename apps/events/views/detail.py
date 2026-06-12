"""GET /api/events/{id} — карточка события."""

from __future__ import annotations

from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny

from apps.events.serializers import EventDetailSerializer
from apps.events.services.exceptions import EventNotFound
from apps.events.services.query import build_detail_queryset

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer


@extend_schema(
    tags=["events"],
    summary="Карточка события",
    description=(
        "Полная карточка события по id: описание, место, время, обложка и "
        "attendance-информация (`attendees_count`, `is_going` для текущего "
        "пользователя, превью друзей-участников). Доступна всем (AllowAny); для "
        "анонимов `is_going=false` и список друзей пуст.\n\n"
        "Возвращает 404, если событие не найдено."
    ),
    responses={200: EventDetailSerializer, 404: DetailSerializer},
)
class EventDetailView(RetrieveAPIView):
    permission_classes = (AllowAny,)
    serializer_class = EventDetailSerializer

    def get_queryset(self):
        return build_detail_queryset()

    def get_object(self):
        queryset = self.get_queryset()
        try:
            return queryset.get(pk=self.kwargs["pk"])
        except queryset.model.DoesNotExist as e:
            raise EventNotFound() from e