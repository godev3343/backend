"""
GET /api/feed — лента чек-инов друзей.

Свои чек-ины НЕ включаем — для них есть /api/checkins/me. Если потом захотим
смешанную ленту "я + друзья" — добавим query-param `include_self=true`.

Дружба — accepted-запись в любом направлении. Используем подзапрос для
получения friend_ids, чтобы не загружать список друзей в Python.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Q
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.checkins.models import CheckIn, Like
from apps.checkins.pagination import CheckInCursorPagination
from apps.checkins.serializers import CheckInSerializer
from apps.social.models import Friendship, FriendshipStatus

if TYPE_CHECKING:
    from rest_framework.request import Request


class FeedView(ListAPIView):
    """GET /api/feed?cursor=...&limit=20"""

    permission_classes = (IsAuthenticated,)
    pagination_class = CheckInCursorPagination
    serializer_class = CheckInSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        user_id = self.request.user.pk

        # Подзапросы вместо values_list+list() — чтобы Postgres сам JOIN'ил
        # без round-trip за списком ID.
        outgoing_friends = Friendship.objects.filter(
            from_user_id=user_id, status=FriendshipStatus.ACCEPTED
        ).values("to_user_id")
        incoming_friends = Friendship.objects.filter(
            to_user_id=user_id, status=FriendshipStatus.ACCEPTED
        ).values("from_user_id")

        return (
            CheckIn.objects.filter(
                Q(user_id__in=outgoing_friends) | Q(user_id__in=incoming_friends)
            )
            .select_related("user", "user__avatar_asset", "place")
            .select_related("photo", "photo__asset")
            .order_by("-created_at", "-id")
        )

    def list(self, request: Request, *args, **kwargs):  # type: ignore[no-untyped-def]
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            liked_ids = self._collect_liked_ids(user_id=request.user.pk, checkins=page)
            serializer = self.get_serializer(
                page,
                many=True,
                context={"liked_ids": liked_ids, "request": request},
            )
            return self.get_paginated_response(serializer.data)

        # На случай если пагинатор отключен или вернул None.
        items = list(queryset)
        liked_ids = self._collect_liked_ids(user_id=request.user.pk, checkins=items)
        serializer = self.get_serializer(
            items,
            many=True,
            context={"liked_ids": liked_ids, "request": request},
        )
        from rest_framework.response import Response

        return Response(serializer.data)

    @staticmethod
    def _collect_liked_ids(*, user_id: int, checkins) -> set[int]:  # type: ignore[no-untyped-def]
        if not checkins:
            return set()
        checkin_ids = [c.pk for c in checkins]
        return set(
            Like.objects.filter(user_id=user_id, checkin_id__in=checkin_ids).values_list(
                "checkin_id", flat=True
            )
        )
