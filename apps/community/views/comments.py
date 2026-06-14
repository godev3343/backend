"""
GET  /api/posts/{id}/comments  — плоский список комментариев (created_at asc).
POST /api/posts/{id}/comments  — добавить комментарий (author из JWT).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.community.models import PostComment
from apps.community.pagination import PostCommentCursorPagination
from apps.community.serializers import (
    CommentCreateSerializer,
    PostCommentSerializer,
)
from apps.community.services import CommentService

if TYPE_CHECKING:
    from uuid import UUID

    from rest_framework.request import Request


@extend_schema(tags=["community"])
class CommentListCreateView(ListAPIView):
    """Список и создание комментариев поста."""

    permission_classes = (IsAuthenticated,)
    pagination_class = PostCommentCursorPagination
    serializer_class = PostCommentSerializer

    def get_throttles(self):  # type: ignore[no-untyped-def]
        if self.request.method == "POST":
            self.throttle_scope = "post_comment"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):  # type: ignore[no-untyped-def]
        if getattr(self, "swagger_fake_view", False):
            return PostComment.objects.none()
        return CommentService.list_queryset(post_id=self.kwargs["post_id"])

    @extend_schema(
        summary="Комментарии поста",
        description="Плоский список комментариев, created_at asc. Cursor-пагинация.",
        responses={200: PostCommentSerializer(many=True)},
    )
    def list(self, request: Request, *args, **kwargs):  # type: ignore[no-untyped-def]
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            liked = CommentService.collect_liked_comment_ids(user_id=request.user.pk, comments=page)
            serializer = self.get_serializer(
                page,
                many=True,
                context={"liked_comment_ids": liked, "request": request},
            )
            return self.get_paginated_response(serializer.data)

        items = list(queryset)
        liked = CommentService.collect_liked_comment_ids(user_id=request.user.pk, comments=items)
        serializer = self.get_serializer(
            items,
            many=True,
            context={"liked_comment_ids": liked, "request": request},
        )
        return Response(serializer.data)

    @extend_schema(
        summary="Добавить комментарий",
        request=CommentCreateSerializer,
        responses={201: PostCommentSerializer},
    )
    def post(self, request: Request, post_id: UUID) -> Response:
        serializer = CommentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        comment = CommentService.create(
            user=request.user,
            post_id=post_id,
            text=serializer.validated_data["text"],
        )
        output = PostCommentSerializer(
            comment, context={"liked_comment_ids": set(), "request": request}
        ).data
        return Response(output, status=201)
