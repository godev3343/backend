"""
POST /api/posts/{id}/share  — репост (инкремент shares_count).
POST /api/posts/{id}/view   — просмотр (инкремент views_count с дедупом).

Тело ответа клиент не использует; отдаём свежий счётчик для удобства.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.community.models import Post
from apps.community.services import PostService

if TYPE_CHECKING:
    from uuid import UUID

    from rest_framework.request import Request


def _counter(*, post_id: UUID, field: str) -> int:
    return Post.objects.filter(pk=post_id).values_list(field, flat=True).first() or 0


@extend_schema(tags=["community"])
class PostShareView(APIView):
    """Поделиться постом."""

    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "post_interact"

    @extend_schema(summary="Поделиться постом")
    def post(self, request: Request, post_id: UUID) -> Response:
        PostService.share(post_id=post_id)
        return Response(
            {"shares_count": _counter(post_id=post_id, field="shares_count")},
            status=status.HTTP_200_OK,
        )


@extend_schema(tags=["community"])
class PostViewView(APIView):
    """Зарегистрировать просмотр поста."""

    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "post_interact"

    @extend_schema(summary="Просмотр поста")
    def post(self, request: Request, post_id: UUID) -> Response:
        PostService.register_view(user=request.user, post_id=post_id)
        return Response(
            {"views_count": _counter(post_id=post_id, field="views_count")},
            status=status.HTTP_200_OK,
        )
