"""
Маршруты сообщества. Без trailing slash — как media/social, клиент дёргает
пути без слеша (иначе 404 на POST).
"""

from __future__ import annotations

from django.urls import path

from apps.community.views import (
    CommentListCreateView,
    PostCommentLikeView,
    PostDetailView,
    PostLikeView,
    PostListCreateView,
    PostShareView,
    PostViewView,
)

app_name = "community"

urlpatterns = [
    path("posts", PostListCreateView.as_view(), name="post_list_create"),
    path("posts/<uuid:post_id>", PostDetailView.as_view(), name="post_detail"),
    path(
        "posts/<uuid:post_id>/comments",
        CommentListCreateView.as_view(),
        name="post_comments",
    ),
    path("posts/<uuid:post_id>/like", PostLikeView.as_view(), name="post_like"),
    path(
        "posts/<uuid:post_id>/comments/<uuid:comment_id>/like",
        PostCommentLikeView.as_view(),
        name="post_comment_like",
    ),
    path("posts/<uuid:post_id>/share", PostShareView.as_view(), name="post_share"),
    path("posts/<uuid:post_id>/view", PostViewView.as_view(), name="post_view"),
]
