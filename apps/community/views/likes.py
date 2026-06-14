"""
Лайки постов и комментариев. Идемпотентны; тело ответа клиент не парсит, но
отдаём свежий счётчик для удобства.

POST   /api/posts/{id}/like                       → 201/200
DELETE /api/posts/{id}/like                       → 204
POST   /api/posts/{id}/comments/{cid}/like        → 201/200
DELETE /api/posts/{id}/comments/{cid}/like        → 204
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.community.services import (
    LikeResult,
    PostCommentLikeService,
    PostLikeService,
)

if TYPE_CHECKING:
    from uuid import UUID

    from rest_framework.request import Request


@extend_schema(tags=["community"])
class PostLikeView(APIView):
    """Лайк/анлайк поста."""

    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "post_interact"

    @extend_schema(summary="Лайкнуть пост")
    def post(self, request: Request, post_id: UUID) -> Response:
        result = PostLikeService.like(user=request.user, post_id=post_id)
        code = status.HTTP_201_CREATED if result == LikeResult.CREATED else status.HTTP_200_OK
        return Response(
            {
                "is_liked": True,
                "likes_count": PostLikeService.likes_count(post_id=post_id),
            },
            status=code,
        )

    @extend_schema(summary="Убрать лайк поста")
    def delete(self, request: Request, post_id: UUID) -> Response:
        PostLikeService.unlike(user=request.user, post_id=post_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["community"])
class PostCommentLikeView(APIView):
    """Лайк/анлайк комментария."""

    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "post_interact"

    @extend_schema(summary="Лайкнуть комментарий")
    def post(self, request: Request, post_id: UUID, comment_id: UUID) -> Response:
        result = PostCommentLikeService.like(
            user=request.user, post_id=post_id, comment_id=comment_id
        )
        code = status.HTTP_201_CREATED if result == LikeResult.CREATED else status.HTTP_200_OK
        return Response(
            {
                "is_liked": True,
                "likes_count": PostCommentLikeService.likes_count(comment_id=comment_id),
            },
            status=code,
        )

    @extend_schema(summary="Убрать лайк комментария")
    def delete(self, request: Request, post_id: UUID, comment_id: UUID) -> Response:
        PostCommentLikeService.unlike(user=request.user, post_id=post_id, comment_id=comment_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
