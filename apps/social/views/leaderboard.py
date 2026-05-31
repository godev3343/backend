"""
Лидерборды по поинтам:
- GET /api/leaderboard          — среди всех пользователей
- GET /api/leaderboard/friends  — среди друзей (+ сам юзер)

rank — позиционный от offset. При равных поинтах ранги различаются по порядку
сортировки; для pre-MVP приемлемо (см. LeaderboardService).
"""
from __future__ import annotations

from rest_framework.generics import GenericAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer, EmptySerializer
from apps.social.serializers.leaderboard import LeaderboardRowSerializer
from apps.social.services.leaderboard import LeaderboardService
from apps.users.permissions import IsEmailVerified, IsOnboarded

_PROTECTED = [IsAuthenticated, IsEmailVerified, IsOnboarded]


class _BaseLeaderboardView(GenericAPIView):
    permission_classes = _PROTECTED
    pagination_class = LimitOffsetPagination
    serializer_class = LeaderboardRowSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    def get(self, request: Request) -> Response:
        qs = self.get_queryset()
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        # paginator.offset уже распаршен из query-параметра в paginate_queryset
        offset = paginator.offset
        for i, user in enumerate(page):
            user.rank = offset + i + 1  # динамический атрибут, не сохраняется
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
class GlobalLeaderboardView(_BaseLeaderboardView):
    """GET /api/leaderboard — все пользователи по поинтам."""

    def get_queryset(self):  # type: ignore[no-untyped-def]
        if getattr(self, "swagger_fake_view", False):
            return LeaderboardService.global_qs().none()
        return LeaderboardService.global_qs()


@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
class FriendsLeaderboardView(_BaseLeaderboardView):
    """GET /api/leaderboard/friends — сам юзер + друзья по поинтам."""

    def get_queryset(self):  # type: ignore[no-untyped-def]
        if getattr(self, "swagger_fake_view", False):
            return LeaderboardService.global_qs().none()
        return LeaderboardService.friends_qs(user=self.request.user)