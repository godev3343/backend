"""
Модели «Сообщества» — Threads-подобная лента.

Сущности:
- Post — пост с текстом и медиа (фото/видео), денормализованные счётчики.
- PostMedia — вложение поста; url/thumbnail_url/aspect_ratio денормализованы
  при создании (из MediaAsset), чтобы лента не делала лишних запросов.
- PostComment — плоский (без веток) комментарий.
- PostLike / PostCommentLike — лайки (идемпотентны через unique).
- PostView — просмотр с дедупом по (post, user, день) — антинакрутка.

id поста и комментария — UUID (DRF сериализует строкой). author.id — числовой
user id. Счётчики обновляются в транзакции на событиях, не COUNT(*) на чтение.
"""

from __future__ import annotations

from uuid import uuid4

from django.conf import settings
from django.db import models

from apps.core.models import CreatedAtModel
from apps.media.models import MediaAsset


class PostMediaType(models.TextChoices):
    IMAGE = "image", "Image"
    VIDEO = "video", "Video"


class Post(CreatedAtModel):
    """Пост сообщества. created_at — из CreatedAtModel (db_index)."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_posts",
    )
    text = models.TextField(blank=True, default="")

    # Денормализованные счётчики — обновляются в транзакции на событиях.
    likes_count = models.PositiveIntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
    shares_count = models.PositiveIntegerField(default=0)
    views_count = models.PositiveBigIntegerField(default=0)

    class Meta:
        db_table = "community_post"
        indexes = [
            # Cursor-пагинация ленты идёт по (-created_at, -id).
            models.Index(fields=("-created_at", "-id"), name="post_created_idx"),
            models.Index(fields=("author", "-created_at"), name="post_author_created_idx"),
        ]

    def __str__(self) -> str:
        return f"Post#{self.pk} author={self.author_id}"


class PostMedia(models.Model):
    """
    Вложение поста. type определяет источник url:
    - image → url = url_feed (webp-вариант после обработки), thumbnail_url пуст.
    - video → url = url_original (mp4 как есть), thumbnail_url — постер (пока пуст).

    url/thumbnail_url/aspect_ratio денормализованы при создании поста, чтобы
    рендер ленты не лез в MediaAsset (N+1). asset — мягкая ссылка для трейсинга;
    при удалении asset'а пост не ломается (url уже сохранён).
    """

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="media",
    )
    asset = models.ForeignKey(
        MediaAsset,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    type = models.CharField(max_length=8, choices=PostMediaType.choices)
    key = models.CharField(max_length=500)
    url = models.URLField(max_length=1000)
    thumbnail_url = models.URLField(max_length=1000, blank=True, default="")
    aspect_ratio = models.FloatField(default=0.8)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "community_post_media"
        ordering = ("position", "id")
        indexes = [
            models.Index(fields=("post", "position"), name="postmedia_post_pos_idx"),
        ]

    def __str__(self) -> str:
        return f"PostMedia#{self.pk} post={self.post_id} type={self.type}"


class PostComment(CreatedAtModel):
    """Плоский комментарий (без веток)."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_comments",
    )
    text = models.TextField()
    likes_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "community_post_comment"
        indexes = [
            # Комментарии отдаются created_at asc — индекс под пагинацию.
            models.Index(
                fields=("post", "created_at", "id"),
                name="comment_post_created_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"PostComment#{self.pk} post={self.post_id}"


class PostLike(CreatedAtModel):
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_post_likes",
    )

    class Meta:
        db_table = "community_post_like"
        constraints = [
            models.UniqueConstraint(
                fields=("post", "user"),
                name="post_like_unique_post_user",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "post"), name="post_like_user_post_idx"),
        ]


class PostCommentLike(CreatedAtModel):
    comment = models.ForeignKey(
        PostComment,
        on_delete=models.CASCADE,
        related_name="likes",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_comment_likes",
    )

    class Meta:
        db_table = "community_post_comment_like"
        constraints = [
            models.UniqueConstraint(
                fields=("comment", "user"),
                name="comment_like_unique_comment_user",
            ),
        ]
        indexes = [
            models.Index(fields=("user", "comment"), name="comment_like_user_comment_idx"),
        ]


class PostView(CreatedAtModel):
    """
    Просмотр поста. Дедуп по (post, user, day) — повторный вход в тот же день
    не накручивает views_count. day — локальная дата (Asia/Almaty).
    """

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="views",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_post_views",
    )
    day = models.DateField(db_index=True)

    class Meta:
        db_table = "community_post_view"
        constraints = [
            models.UniqueConstraint(
                fields=("post", "user", "day"),
                name="post_view_unique_post_user_day",
            ),
        ]
