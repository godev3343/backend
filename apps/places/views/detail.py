"""GET /api/places/{id} — полная карточка места."""

from __future__ import annotations

from django.db.models import Prefetch
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.checkins.models import CheckIn
from apps.places.models import Place, PlacePhoto
from apps.places.serializers import PlaceDetailSerializer
from apps.places.services.exceptions import PlaceNotFound
from apps.places.services.query import build_detail_queryset

# Сколько последних чек-инов показывать в карточке места.
RECENT_CHECKINS_LIMIT = 5


class PlaceDetailView(GenericAPIView):
    permission_classes = (AllowAny,)
    serializer_class = PlaceDetailSerializer

    def get(self, request: Request, pk: int) -> Response:
        photos_qs = PlacePhoto.objects.select_related("asset").order_by("-created_at", "-id")

        try:
            place = (
                build_detail_queryset()
                .prefetch_related(
                    "vibes",
                    Prefetch("photos", queryset=photos_qs),
                )
                .get(pk=pk)
            )
        except Place.DoesNotExist as e:
            raise PlaceNotFound() from e

        # recent_checkins: отдельный запрос с лимитом.
        # Делаем НЕ через Prefetch(...[:N]) — Django применяет slice к JOIN'у
        # для всего набора Place'ов, не per-place. На single-get это случайно
        # работает, но паттерн опасный — оставляем как явный запрос.
        place._recent_checkins = list(  # type: ignore[attr-defined]
            CheckIn.objects.filter(place=place)
            .select_related("user")
            .order_by("-created_at", "-id")[:RECENT_CHECKINS_LIMIT]
        )

        serializer = self.serializer_class(place)
        return Response(serializer.data)
