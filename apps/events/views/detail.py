"""GET /api/events/{id} — карточка события."""

from __future__ import annotations

from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny

from apps.events.serializers import EventDetailSerializer
from apps.events.services.exceptions import EventNotFound
from apps.events.services.query import build_detail_queryset

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer, EmptySerializer


@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
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