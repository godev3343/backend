# apps/places/views/detail.py
"""GET /api/places/{id} — полная карточка места."""

from __future__ import annotations

from django.db.models import Prefetch
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import AllowAny

from apps.checkins.models import CheckIn
from apps.places.models import Place, PlacePhoto
from apps.places.serializers import PlaceDetailSerializer
from apps.places.services.exceptions import PlaceNotFound
from apps.places.services.query import build_detail_queryset

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer

# Сколько последних чек-инов показывать в карточке места.
RECENT_CHECKINS_LIMIT = 5


@extend_schema(
    tags=["places"],
    summary="Карточка места",
    description=(
        "Полная карточка заведения по id: адрес, телефон, часы работы, описание, "
        "категория, вайбы (отсортированы по весу), обработанные фото и последние "
        f"{RECENT_CHECKINS_LIMIT} чек-инов.\n\n"
        "Доступна всем (AllowAny). Возвращает 404, если место не найдено."
    ),
    responses={200: PlaceDetailSerializer, 404: DetailSerializer},
)
class PlaceDetailView(RetrieveAPIView):
    permission_classes = (AllowAny,)
    serializer_class = PlaceDetailSerializer

    def get_queryset(self):
        photos_qs = PlacePhoto.objects.select_related("asset").order_by("-created_at", "-id")
        return build_detail_queryset().prefetch_related(
            "vibes",
            Prefetch("photos", queryset=photos_qs),
        )

    def get_object(self) -> Place:
        try:
            place = self.get_queryset().get(pk=self.kwargs["pk"])
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
        return place