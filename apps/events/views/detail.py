"""GET /api/events/{id} — карточка события."""
from __future__ import annotations

from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.events.models import Event
from apps.events.serializers import EventDetailSerializer
from apps.events.services.exceptions import EventNotFound
from apps.events.services.query import build_detail_queryset


class EventDetailView(GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = EventDetailSerializer

    def get(self, request: Request, pk: int) -> Response:
        try:
            event = build_detail_queryset().get(pk=pk)
        except Event.DoesNotExist as e:
            raise EventNotFound() from e

        return Response(self.serializer_class(event).data)