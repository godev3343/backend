"""
PostService — лента, создание постов (сборка медиа из ключей), просмотры, репосты.

Контракт медиа: клиент грузит файлы существующим media-пайплайном
(presign→R2→confirm) и передаёт сюда только КЛЮЧИ. Asset обязан быть PROCESSED:
для image это feed-вариант + размеры; для video — постер (ffmpeg-кадр в key_feed)
+ размеры кадра. url видео = оригинал (mp4), thumbnail_url = постер (url_feed).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from django.db import transaction
from django.db.models import F, Q, QuerySet
from django.utils import timezone

from apps.community.models import (
    Post,
    PostLike,
    PostMedia,
    PostMediaType,
    PostView,
)
from apps.community.services.exceptions import (
    PostMediaNotFound,
    PostMediaNotReady,
    PostNotFound,
)
from apps.media.models import MediaAsset, MediaPurpose, MediaStatus
from apps.social.models import Friendship, FriendshipStatus

if TYPE_CHECKING:
    from apps.users.models import User

DEFAULT_ASPECT_RATIO = 0.8

# type вложения → purpose, который должен быть у MediaAsset.
_TYPE_TO_PURPOSE = {
    PostMediaType.IMAGE: MediaPurpose.POST_IMAGE,
    PostMediaType.VIDEO: MediaPurpose.POST_VIDEO,
}


class PostService:
    """Stateless — все методы classmethod/staticmethod."""

    # ---- queries --------------------------------------------------------

    @staticmethod
    def _base_queryset() -> QuerySet[Post]:
        return (
            Post.objects.select_related("author", "author__avatar_asset")
            .prefetch_related("media")
            .order_by("-created_at", "-id")
        )

    @classmethod
    def feed_queryset(cls, *, user: User, scope: str) -> QuerySet[Post]:
        """
        scope=all — все посты сообщества.
        scope=friends — посты взаимных друзей + свои.
        """
        qs = cls._base_queryset()
        if scope == "friends":
            user_id = user.pk
            outgoing = Friendship.objects.filter(
                from_user_id=user_id, status=FriendshipStatus.ACCEPTED
            ).values("to_user_id")
            incoming = Friendship.objects.filter(
                to_user_id=user_id, status=FriendshipStatus.ACCEPTED
            ).values("from_user_id")
            qs = qs.filter(
                Q(author_id__in=outgoing) | Q(author_id__in=incoming) | Q(author_id=user_id)
            )
        return qs

    @classmethod
    def get_post(cls, *, post_id: UUID) -> Post:
        """
        Raises:
            PostNotFound
        """
        post = cls._base_queryset().filter(pk=post_id).first()
        if post is None:
            raise PostNotFound()
        return post

    @staticmethod
    def collect_liked_post_ids(*, user_id: int, posts: list[Post]) -> set[UUID]:
        """Один запрос: какие из постов страницы лайкнул юзер."""
        if not posts:
            return set()
        post_ids = [p.pk for p in posts]
        return set(
            PostLike.objects.filter(user_id=user_id, post_id__in=post_ids).values_list(
                "post_id", flat=True
            )
        )

    # ---- create ---------------------------------------------------------

    @classmethod
    @transaction.atomic
    def create(
        cls,
        *,
        user: User,
        text: str,
        media_items: list[dict[str, Any]],
    ) -> Post:
        """
        Создаёт пост и его медиа из ключей. Возвращает пост, готовый к
        сериализации (media prefetched).

        Raises:
            PostMediaNotFound — ключ не найден / чужой / не тот тип.
            PostMediaNotReady — asset ещё не обработан.
        """
        post = Post.objects.create(author=user, text=text)

        media_rows: list[PostMedia] = []
        for position, item in enumerate(media_items):
            media_type = item["type"]
            asset = cls._resolve_asset(user=user, key=item["key"], media_type=media_type)
            media_rows.append(
                PostMedia(
                    post=post,
                    asset=asset,
                    type=media_type,
                    key=asset.key_original,
                    url=cls._media_url(asset=asset, media_type=media_type),
                    thumbnail_url=cls._media_thumbnail(asset=asset, media_type=media_type),
                    aspect_ratio=cls._aspect_ratio(asset),
                    position=position,
                )
            )

        if media_rows:
            PostMedia.objects.bulk_create(media_rows)

        # Перечитываем с prefetch, чтобы media пришли отсортированными и без N+1.
        return cls.get_post(post_id=post.pk)

    @staticmethod
    def _resolve_asset(*, user: User, key: str, media_type: str) -> MediaAsset:
        purpose = _TYPE_TO_PURPOSE[media_type]
        # Клиент шлёт presign-ключ (.../{uuid}/original.jpg). process_image мог
        # переписать оригинал в .webp при даунскейле (>2048px), поэтому матчим
        # по префиксу ассета (.../{uuid}/), а не по точному имени файла. uuid
        # уникален на presign — коллизий нет. Видео-ключ не переписывается.
        prefix = key.rsplit("/", 1)[0] + "/"
        asset = (
            MediaAsset.objects.filter(key_original__startswith=prefix, owner=user, purpose=purpose)
            .order_by("pk")
            .first()
        )
        if asset is None:
            raise PostMediaNotFound()
        if asset.status != MediaStatus.PROCESSED:
            raise PostMediaNotReady()
        return asset

    @staticmethod
    def _media_url(*, asset: MediaAsset, media_type: str) -> str:
        # Видео — отдаём оригинал (mp4 как залит); фото — webp feed-вариант.
        if media_type == PostMediaType.VIDEO:
            return asset.url_original
        return asset.url_feed

    @staticmethod
    def _media_thumbnail(*, asset: MediaAsset, media_type: str) -> str:
        # Видео: постер — feed-вариант кадра (process_video кладёт его в key_feed,
        # ~1080px). Фото: thumbnail не нужен, клиент берёт url.
        if media_type == PostMediaType.VIDEO:
            return asset.url_feed if asset.key_feed else ""
        return ""

    @staticmethod
    def _aspect_ratio(asset: MediaAsset) -> float:
        if asset.width and asset.height:
            return round(asset.width / asset.height, 4)
        return DEFAULT_ASPECT_RATIO

    # ---- views / shares -------------------------------------------------

    @classmethod
    @transaction.atomic
    def register_view(cls, *, user: User, post_id: UUID) -> None:
        """
        Дедуп по (post, user, день): повторный просмотр за день не накручивает.

        Raises:
            PostNotFound
        """
        if not Post.objects.filter(pk=post_id).exists():
            raise PostNotFound()

        _, created = PostView.objects.get_or_create(
            post_id=post_id,
            user=user,
            day=timezone.localdate(),
        )
        if created:
            Post.objects.filter(pk=post_id).update(views_count=F("views_count") + 1)

    @classmethod
    @transaction.atomic
    def share(cls, *, post_id: UUID) -> None:
        """
        Raises:
            PostNotFound
        """
        if not Post.objects.filter(pk=post_id).exists():
            raise PostNotFound()
        Post.objects.filter(pk=post_id).update(shares_count=F("shares_count") + 1)
