"""
Эндпоинты дружбы:
- POST   /api/friends/requests              (send)
- GET    /api/friends/requests/incoming
- GET    /api/friends/requests/outgoing
- POST   /api/friends/requests/{id}/accept
- POST   /api/friends/requests/{id}/decline
- DELETE /api/friends/requests/{id}         (cancel outgoing)
- GET    /api/friends
- DELETE /api/friends/{user_id}             (remove friend)

Все требуют IsEmailVerified + IsOnboarded — чтобы не создавать связи
до подтверждения личности юзера.
"""

from __future__ import annotations

from rest_framework import serializers, status
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.social.models import Friendship
from apps.social.serializers import (
    FriendListItemSerializer,
    IncomingFriendRequestSerializer,
    OutgoingFriendRequestSerializer,
    SendFriendRequestSerializer,
)
from apps.social.services import FriendshipService
from apps.social.throttling import FriendRequestThrottle
from apps.users.permissions import IsEmailVerified, IsOnboarded

from drf_spectacular.utils import extend_schema, inline_serializer

from apps.core.serializers import DetailSerializer

_PROTECTED = [IsAuthenticated, IsEmailVerified, IsOnboarded]

# Ответ на действия с заявкой/дружбой: id связи и её текущий статус
# (pending / accepted). Хватает фронту, чтобы перерисовать кнопку.
_FriendshipActionSerializer = inline_serializer(
    name="FriendshipAction",
    fields={
        "id": serializers.IntegerField(),
        "status": serializers.ChoiceField(choices=["pending", "accepted"]),
    },
)


@extend_schema(
    tags=["social"],
    summary="Отправить заявку в друзья",
    description=(
        "Отправляет заявку в друзья пользователю `to_user_id`. Если от этого "
        "пользователя уже есть встречная заявка, дружба подтверждается "
        "автоматически и в ответе будет `status=accepted`.\n\n"
        "Требует подтверждённого email и пройденного онбординга. Throttling по "
        "пользователю."
    ),
    request=SendFriendRequestSerializer,
    responses={
        201: _FriendshipActionSerializer,
        400: DetailSerializer,
        401: DetailSerializer,
        403: DetailSerializer,
        404: DetailSerializer,
        429: DetailSerializer,
    },
)
class FriendRequestCreateView(APIView):
    """POST /api/friends/requests — отправить заявку."""

    permission_classes = _PROTECTED
    throttle_classes = [FriendRequestThrottle]

    def post(self, request: Request) -> Response:
        serializer = SendFriendRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        friendship = FriendshipService.send_request(
            from_user=request.user,
            to_user_id=serializer.validated_data["to_user_id"],
        )
        # Возвращаем минимум — id и status. Фронту обычно достаточно,
        # чтобы поменять кнопку. Если accept был автоматический (встречная
        # pending), status будет "accepted".
        return Response(
            {"id": friendship.pk, "status": friendship.status},
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["social"],
    summary="Входящие заявки в друзья",
    description=(
        "Список заявок в друзья, где текущий пользователь — получатель "
        "(`status=pending`). Показывает отправителя каждой заявки. "
        "Пагинация limit/offset."
    ),
    responses={200: IncomingFriendRequestSerializer(many=True), 401: DetailSerializer},
)
class IncomingFriendRequestsView(GenericAPIView):
    """GET /api/friends/requests/incoming — pending где я to_user."""

    permission_classes = _PROTECTED
    pagination_class = LimitOffsetPagination
    serializer_class = IncomingFriendRequestSerializer
    queryset = Friendship.objects.none()  # для генерации схемы drf-spectacular

    def get(self, request: Request) -> Response:
        qs = FriendshipService.incoming_requests(user=request.user)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        # Не пихаем .from_user в payload как FK — кастомный сериализатор
        # сам разрулит через _UserBriefSerializer
        data = [
            {
                "id": f.pk,
                "from_user": f.from_user,
                "created_at": f.created_at,
            }
            for f in page
        ]
        serializer = self.get_serializer(data, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(
    tags=["social"],
    summary="Исходящие заявки в друзья",
    description=(
        "Список заявок в друзья, отправленных текущим пользователем и ещё не "
        "принятых (`status=pending`). Показывает получателя каждой заявки. "
        "Пагинация limit/offset."
    ),
    responses={200: OutgoingFriendRequestSerializer(many=True), 401: DetailSerializer},
)
class OutgoingFriendRequestsView(GenericAPIView):
    """GET /api/friends/requests/outgoing — pending где я from_user."""

    permission_classes = _PROTECTED
    pagination_class = LimitOffsetPagination
    serializer_class = OutgoingFriendRequestSerializer
    queryset = Friendship.objects.none()  # для генерации схемы drf-spectacular

    def get(self, request: Request) -> Response:
        qs = FriendshipService.outgoing_requests(user=request.user)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = [
            {
                "id": f.pk,
                "to_user": f.to_user,
                "created_at": f.created_at,
            }
            for f in page
        ]
        serializer = self.get_serializer(data, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(
    tags=["social"],
    summary="Принять заявку в друзья",
    description=(
        "Принимает входящую заявку по её id. После этого пользователи становятся "
        "друзьями (`status=accepted`). Принять можно только заявку, адресованную "
        "текущему пользователю."
    ),
    request=None,
    responses={
        200: _FriendshipActionSerializer,
        401: DetailSerializer,
        403: DetailSerializer,
        404: DetailSerializer,
    },
)
class FriendRequestAcceptView(APIView):
    """POST /api/friends/requests/{id}/accept."""

    permission_classes = _PROTECTED

    def post(self, request: Request, friendship_id: int) -> Response:
        f = FriendshipService.accept_request(user=request.user, friendship_id=friendship_id)
        return Response({"id": f.pk, "status": f.status}, status=status.HTTP_200_OK)


@extend_schema(
    tags=["social"],
    summary="Отклонить заявку в друзья",
    description=(
        "Отклоняет входящую заявку по её id (запись удаляется). Отклонить можно "
        "только заявку, адресованную текущему пользователю. Идемпотентно "
        "возвращает 204."
    ),
    request=None,
    responses={204: None, 401: DetailSerializer, 403: DetailSerializer, 404: DetailSerializer},
)
class FriendRequestDeclineView(APIView):
    """POST /api/friends/requests/{id}/decline — hard delete."""

    permission_classes = _PROTECTED

    def post(self, request: Request, friendship_id: int) -> Response:
        FriendshipService.decline_request(user=request.user, friendship_id=friendship_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["social"],
    summary="Отменить исходящую заявку",
    description=(
        "Отменяет собственную исходящую заявку по её id (запись удаляется). "
        "Отменить можно только заявку, отправленную текущим пользователем."
    ),
    responses={204: None, 401: DetailSerializer, 403: DetailSerializer, 404: DetailSerializer},
)
class FriendRequestCancelView(APIView):
    """DELETE /api/friends/requests/{id} — отменить свою исходящую."""

    permission_classes = _PROTECTED

    def delete(self, request: Request, friendship_id: int) -> Response:
        FriendshipService.cancel_request(user=request.user, friendship_id=friendship_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["social"],
    summary="Список друзей",
    description=(
        "Список друзей текущего пользователя (подтверждённые связи). Каждый "
        "элемент — встречный пользователь с краткой публичной информацией и "
        "статусом по поинтам. Пагинация limit/offset."
    ),
    responses={200: FriendListItemSerializer(many=True), 401: DetailSerializer},
)
class FriendListView(GenericAPIView):
    """GET /api/friends — список друзей."""

    permission_classes = _PROTECTED
    pagination_class = LimitOffsetPagination
    serializer_class = FriendListItemSerializer
    queryset = Friendship.objects.none()  # для генерации схемы drf-spectacular

    def get(self, request: Request) -> Response:
        qs = FriendshipService.list_friends(user=request.user)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(
    tags=["social"],
    summary="Удалить из друзей",
    description=(
        "Удаляет дружескую связь с пользователем `user_id` (в обе стороны). "
        "Идемпотентно: если связи нет, всё равно возвращается 204."
    ),
    responses={204: None, 401: DetailSerializer, 403: DetailSerializer},
)
class FriendRemoveView(APIView):
    """DELETE /api/friends/{user_id} — удалить из друзей."""

    permission_classes = _PROTECTED

    def delete(self, request: Request, user_id: int) -> Response:
        FriendshipService.remove_friend(user=request.user, other_user_id=user_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
