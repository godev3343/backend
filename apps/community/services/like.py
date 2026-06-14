"""
Лайки постов и комментариев. Идемпотентны через unique-констрейнт.
Счётчик инкрементим/декрементим через F() (атомарно, без гонок).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import F
from django.db.models.functions import Greatest

from apps.community.models import (
    Post,
    PostComment,
    PostCommentLike,
    PostLike,
)
from apps.community.services.exceptions import CommentNotFound, PostNotFound

if TYPE_CHECKING:
    from apps.users.models import User


class LikeResult:
    """Результат like()/unlike() — определяет статус-код во view."""

    CREATED = "created"
    ALREADY_LIKED = "already_liked"
    REMOVED = "removed"
    WAS_NOT_LIKED = "was_not_liked"


class PostLikeService:
    """Stateless — все методы classmethod."""

    @classmethod
    @transaction.atomic
    def like(cls, *, user: User, post_id: UUID) -> str:
        """
        Идемпотентно: повторный лайк не множит счётчик.

        Raises:
            PostNotFound
        """
        if not Post.objects.filter(pk=post_id).exists():
            raise PostNotFound()

        try:
            PostLike.objects.create(user=user, post_id=post_id)
        except IntegrityError:
            return LikeResult.ALREADY_LIKED

        Post.objects.filter(pk=post_id).update(likes_count=F("likes_count") + 1)
        return LikeResult.CREATED

    @classmethod
    @transaction.atomic
    def unlike(cls, *, user: User, post_id: UUID) -> str:
        """
        Raises:
            PostNotFound
        """
        if not Post.objects.filter(pk=post_id).exists():
            raise PostNotFound()

        deleted, _ = PostLike.objects.filter(user=user, post_id=post_id).delete()
        if deleted == 0:
            return LikeResult.WAS_NOT_LIKED

        Post.objects.filter(pk=post_id).update(likes_count=Greatest(F("likes_count") - 1, 0))
        return LikeResult.REMOVED

    @staticmethod
    def likes_count(*, post_id: UUID) -> int:
        return Post.objects.filter(pk=post_id).values_list("likes_count", flat=True).first() or 0


class PostCommentLikeService:
    """Лайки комментариев. comment_id вложен в URL под post_id."""

    @classmethod
    @transaction.atomic
    def like(cls, *, user: User, post_id: UUID, comment_id: UUID) -> str:
        """
        Raises:
            CommentNotFound — нет комментария с таким id у этого поста.
        """
        if not PostComment.objects.filter(pk=comment_id, post_id=post_id).exists():
            raise CommentNotFound()

        try:
            PostCommentLike.objects.create(user=user, comment_id=comment_id)
        except IntegrityError:
            return LikeResult.ALREADY_LIKED

        PostComment.objects.filter(pk=comment_id).update(likes_count=F("likes_count") + 1)
        return LikeResult.CREATED

    @classmethod
    @transaction.atomic
    def unlike(cls, *, user: User, post_id: UUID, comment_id: UUID) -> str:
        """
        Raises:
            CommentNotFound
        """
        if not PostComment.objects.filter(pk=comment_id, post_id=post_id).exists():
            raise CommentNotFound()

        deleted, _ = PostCommentLike.objects.filter(user=user, comment_id=comment_id).delete()
        if deleted == 0:
            return LikeResult.WAS_NOT_LIKED

        PostComment.objects.filter(pk=comment_id).update(
            likes_count=Greatest(F("likes_count") - 1, 0)
        )
        return LikeResult.REMOVED

    @staticmethod
    def likes_count(*, comment_id: UUID) -> int:
        return (
            PostComment.objects.filter(pk=comment_id).values_list("likes_count", flat=True).first()
            or 0
        )
