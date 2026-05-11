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

from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.social.serializers import (
    FriendListItemSerializer,
    IncomingFriendRequestSerializer,
    OutgoingFriendRequestSerializer,
    SendFriendRequestSerializer,
)
from apps.social.services import FriendshipService
from apps.social.throttling import FriendRequestThrottle
from apps.users.permissions import IsEmailVerified, IsOnboarded


_PROTECTED = [IsAuthenticated, IsEmailVerified, IsOnboarded]


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


class IncomingFriendRequestsView(GenericAPIView):
    """GET /api/friends/requests/incoming — pending где я to_user."""

    permission_classes = _PROTECTED
    pagination_class = LimitOffsetPagination
    serializer_class = IncomingFriendRequestSerializer

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


class OutgoingFriendRequestsView(GenericAPIView):
    """GET /api/friends/requests/outgoing — pending где я from_user."""

    permission_classes = _PROTECTED
    pagination_class = LimitOffsetPagination
    serializer_class = OutgoingFriendRequestSerializer

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


class FriendRequestAcceptView(APIView):
    """POST /api/friends/requests/{id}/accept."""

    permission_classes = _PROTECTED

    def post(self, request: Request, friendship_id: int) -> Response:
        f = FriendshipService.accept_request(
            user=request.user, friendship_id=friendship_id
        )
        return Response(
            {"id": f.pk, "status": f.status}, status=status.HTTP_200_OK
        )


class FriendRequestDeclineView(APIView):
    """POST /api/friends/requests/{id}/decline — hard delete."""

    permission_classes = _PROTECTED

    def post(self, request: Request, friendship_id: int) -> Response:
        FriendshipService.decline_request(
            user=request.user, friendship_id=friendship_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class FriendRequestCancelView(APIView):
    """DELETE /api/friends/requests/{id} — отменить свою исходящую."""

    permission_classes = _PROTECTED

    def delete(self, request: Request, friendship_id: int) -> Response:
        FriendshipService.cancel_request(
            user=request.user, friendship_id=friendship_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class FriendListView(GenericAPIView):
    """GET /api/friends — список друзей."""

    permission_classes = _PROTECTED
    pagination_class = LimitOffsetPagination
    serializer_class = FriendListItemSerializer

    def get(self, request: Request) -> Response:
        qs = FriendshipService.list_friends(user=request.user)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class FriendRemoveView(APIView):
    """DELETE /api/friends/{user_id} — удалить из друзей."""

    permission_classes = _PROTECTED

    def delete(self, request: Request, user_id: int) -> Response:
        FriendshipService.remove_friend(
            user=request.user, other_user_id=user_id
        )
        return Response(status=status.HTTP_204_NO_CONTENT)