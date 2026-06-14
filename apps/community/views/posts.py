"""
GET  /api/posts?scope=friends|all  — лента (cursor-пагинация).
POST /api/posts                     — создать пост (author из JWT).
GET  /api/posts/{id}                — один пост с актуальными счётчиками.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.community.models import Post
from apps.community.pagination import PostCursorPagination
from apps.community.serializers import PostCreateSerializer, PostSerializer
from apps.community.services import PostService

if TYPE_CHECKING:
    from uuid import UUID

    from rest_framework.request import Request

_ALLOWED_SCOPES = {"friends", "all"}


@extend_schema(tags=["community"])
class PostListCreateView(ListAPIView):
    """Лента постов и создание поста."""

    permission_classes = (IsAuthenticated,)
    pagination_class = PostCursorPagination
    serializer_class = PostSerializer

    def get_throttles(self):  # type: ignore[no-untyped-def]
        # Лимитируем только запись; чтение ленты — под общими user-throttle.
        if self.request.method == "POST":
            self.throttle_scope = "post_create"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):  # type: ignore[no-untyped-def]
        if getattr(self, "swagger_fake_view", False):
            return Post.objects.none()
        return PostService.feed_queryset(user=self.request.user, scope=self._scope())

    def _scope(self) -> str:
        scope = self.request.query_params.get("scope")
        if scope not in _ALLOWED_SCOPES:
            raise ValidationError({"scope": "Required query param, one of: friends, all."})
        return scope

    @extend_schema(
        summary="Лента постов сообщества",
        description=(
            "Лента постов в обратном хронологическом порядке. `scope=friends` — "
            "посты взаимных друзей и свои; `scope=all` — все посты сообщества. "
            "Cursor-пагинация (параметр `cursor`), `is_liked` — для текущего юзера."
        ),
        parameters=[
            OpenApiParameter(
                name="scope",
                required=True,
                enum=sorted(_ALLOWED_SCOPES),
                description="friends — друзья+свои, all — всё сообщество.",
            ),
            OpenApiParameter(name="cursor", required=False),
        ],
        responses={200: PostSerializer(many=True)},
    )
    def list(self, request: Request, *args, **kwargs):  # type: ignore[no-untyped-def]
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)

        if page is not None:
            liked = PostService.collect_liked_post_ids(user_id=request.user.pk, posts=page)
            serializer = self.get_serializer(
                page,
                many=True,
                context={"liked_post_ids": liked, "request": request},
            )
            return self.get_paginated_response(serializer.data)

        items = list(queryset)
        liked = PostService.collect_liked_post_ids(user_id=request.user.pk, posts=items)
        serializer = self.get_serializer(
            items,
            many=True,
            context={"liked_post_ids": liked, "request": request},
        )
        return Response(serializer.data)

    @extend_schema(
        summary="Создать пост",
        description=(
            "Создаёт пост от имени текущего юзера. Медиа передаётся ключами из "
            "media-пайплайна (presign→R2→confirm). Возвращает собранный пост."
        ),
        request=PostCreateSerializer,
        responses={201: PostSerializer},
    )
    def post(self, request: Request, *args, **kwargs):  # type: ignore[no-untyped-def]
        serializer = PostCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        post = PostService.create(
            user=request.user,
            text=serializer.validated_data["text"],
            media_items=serializer.validated_data["media"],
        )
        output = PostSerializer(post, context={"liked_post_ids": set(), "request": request}).data
        return Response(output, status=201)


@extend_schema(tags=["community"])
class PostDetailView(APIView):
    """GET /api/posts/{id}."""

    permission_classes = (IsAuthenticated,)

    @extend_schema(
        summary="Один пост",
        description="Возвращает пост с актуальными счётчиками и `is_liked`.",
        responses={200: PostSerializer},
    )
    def get(self, request: Request, post_id: UUID) -> Response:
        post = PostService.get_post(post_id=post_id)
        liked = PostService.collect_liked_post_ids(user_id=request.user.pk, posts=[post])
        output = PostSerializer(post, context={"liked_post_ids": liked, "request": request}).data
        return Response(output)
