"""
CommentService — плоские комментарии. Создание инкрементит post.comments_count
в той же транзакции (иначе COUNT(*) на каждый элемент ленты).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from django.db import transaction
from django.db.models import F, QuerySet

from apps.community.models import Post, PostComment, PostCommentLike
from apps.community.services.exceptions import PostNotFound

if TYPE_CHECKING:
    from apps.users.models import User


class CommentService:
    """Stateless — все методы classmethod/staticmethod."""

    @staticmethod
    def list_queryset(*, post_id: UUID) -> QuerySet[PostComment]:
        """Комментарии поста, created_at asc (старые сверху)."""
        return (
            PostComment.objects.filter(post_id=post_id)
            .select_related("author", "author__avatar_asset")
            .order_by("created_at", "id")
        )

    @classmethod
    @transaction.atomic
    def create(cls, *, user: User, post_id: UUID, text: str) -> PostComment:
        """
        Создаёт комментарий и бампает post.comments_count.

        Raises:
            PostNotFound
        """
        if not Post.objects.filter(pk=post_id).exists():
            raise PostNotFound()

        comment = PostComment.objects.create(post_id=post_id, author=user, text=text)
        Post.objects.filter(pk=post_id).update(comments_count=F("comments_count") + 1)

        # Перечитываем с select_related, чтобы author сериализовался без N+1.
        return PostComment.objects.select_related("author", "author__avatar_asset").get(
            pk=comment.pk
        )

    @staticmethod
    def collect_liked_comment_ids(*, user_id: int, comments: list[PostComment]) -> set[UUID]:
        """Один запрос: какие из комментариев страницы лайкнул юзер."""
        if not comments:
            return set()
        comment_ids = [c.pk for c in comments]
        return set(
            PostCommentLike.objects.filter(user_id=user_id, comment_id__in=comment_ids).values_list(
                "comment_id", flat=True
            )
        )
