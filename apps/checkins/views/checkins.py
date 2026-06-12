"""
POST /api/checkins        — создать чек-ин.
GET  /api/checkins/me     — история своих.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.generics import GenericAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.checkins.models import CheckIn, Like
from apps.checkins.pagination import CheckInCursorPagination
from apps.checkins.serializers import (
    CheckInCreateSerializer,
    CheckInSerializer,
)
from apps.checkins.services import CheckInService

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer


@extend_schema(
    tags=["checkins"],
    summary="Создать чек-ин",
    description=(
        "Создаёт чек-ин в заведении. Координаты пользователя (`latitude`/"
        "`longitude`) проверяются на близость к месту (гео-гейт) — слишком "
        "далёкий чек-ин отклоняется с 400. Опционально можно приложить "
        "комментарий и фото (`photo_key` из загруженного через `/api/upload/*` "
        "ассета). За чек-ин начисляются поинты.\n\n"
        "Возвращает созданный чек-ин."
    ),
    request=CheckInCreateSerializer,
    responses={201: CheckInSerializer, 400: DetailSerializer, 401: DetailSerializer},
)
class CheckInCreateView(GenericAPIView):
    """
    POST /api/checkins

    Body: place_id, latitude, longitude, comment?, photo_key?
    Response: 201 + CheckInSerializer.
    """

    permission_classes = (IsAuthenticated,)
    serializer_class = CheckInCreateSerializer

    def post(self, request: Request) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        checkin = CheckInService.create(
            user=request.user,
            place_id=data["place_id"],
            latitude=data["latitude"],
            longitude=data["longitude"],
            comment=data.get("comment", ""),
            photo_key=data.get("photo_key"),
        )

        # Догружаем связанные объекты для сериализации, чтобы не плодить
        # отдельные SQL'и в CheckInSerializer.
        checkin = (
            CheckIn.objects.select_related("user", "user__avatar_asset", "place")
            .select_related("photo", "photo__asset")
            .get(pk=checkin.pk)
        )

        output = CheckInSerializer(checkin).data
        return Response(output, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=["checkins"],
    summary="История моих чек-инов",
    description=(
        "Лента собственных чек-инов текущего пользователя в обратном "
        "хронологическом порядке. Cursor-пагинация (параметр `cursor`)."
    ),
)
class MyCheckInsView(ListAPIView):
    """
    GET /api/checkins/me — история своих чек-инов с cursor-пагинацией.

    Свои лайки на свои же чек-ины показываем — теоретически юзер может
    лайкнуть свой чек-ин (мы это не запрещаем; если решим запретить —
    добавим в LikeService).
    """

    permission_classes = (IsAuthenticated,)
    pagination_class = CheckInCursorPagination
    serializer_class = CheckInSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        if getattr(self, "swagger_fake_view", False):
            return CheckIn.objects.none()  # type: ignore[no-untyped-def]
        return (
            CheckIn.objects.filter(user=self.request.user)
            .select_related("user", "user__avatar_asset", "place")
            .select_related("photo", "photo__asset")
            .order_by("-created_at", "-id")
        )

    def get_serializer_context(self) -> dict:
        ctx = super().get_serializer_context()
        # liked_ids — собираем одним запросом для текущей страницы.
        # Page формируется DRF паджинатором; на этом этапе у нас ещё нет
        # доступа к ней. Поэтому переопределяем list() ниже.
        return ctx

    def list(self, request, *args, **kwargs):  # type: ignore[no-untyped-def]
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            liked_ids = self._collect_liked_ids(user_id=request.user.pk, checkins=page)
            serializer = self.get_serializer(
                page, many=True, context={"liked_ids": liked_ids, "request": request}
            )
            return self.get_paginated_response(serializer.data)

        liked_ids = self._collect_liked_ids(user_id=request.user.pk, checkins=list(queryset))
        serializer = self.get_serializer(
            queryset, many=True, context={"liked_ids": liked_ids, "request": request}
        )
        return Response(serializer.data)

    @staticmethod
    def _collect_liked_ids(*, user_id: int, checkins) -> set[int]:  # type: ignore[no-untyped-def]
        """Один запрос: какие из этих checkin-id юзер уже лайкнул."""
        if not checkins:
            return set()
        checkin_ids = [c.pk for c in checkins]
        return set(
            Like.objects.filter(user_id=user_id, checkin_id__in=checkin_ids).values_list(
                "checkin_id", flat=True
            )
        )
