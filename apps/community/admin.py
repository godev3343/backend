from __future__ import annotations

from django.contrib import admin

from apps.community.models import (
    Post,
    PostComment,
    PostCommentLike,
    PostLike,
    PostMedia,
    PostView,
)


class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 0
    raw_id_fields = ("asset",)
    readonly_fields = ("url", "thumbnail_url", "aspect_ratio")


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "author",
        "likes_count",
        "comments_count",
        "shares_count",
        "views_count",
        "created_at",
    )
    search_fields = ("author__email", "author__display_name", "text")
    raw_id_fields = ("author",)
    readonly_fields = (
        "created_at",
        "likes_count",
        "comments_count",
        "shares_count",
        "views_count",
    )
    date_hierarchy = "created_at"
    inlines = (PostMediaInline,)


@admin.register(PostComment)
class PostCommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "author", "likes_count", "created_at")
    search_fields = ("author__email", "author__display_name", "text")
    raw_id_fields = ("post", "author")
    readonly_fields = ("created_at", "likes_count")
    date_hierarchy = "created_at"


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "user", "created_at")
    raw_id_fields = ("post", "user")
    readonly_fields = ("created_at",)


@admin.register(PostCommentLike)
class PostCommentLikeAdmin(admin.ModelAdmin):
    list_display = ("id", "comment", "user", "created_at")
    raw_id_fields = ("comment", "user")
    readonly_fields = ("created_at",)


@admin.register(PostView)
class PostViewAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "user", "day", "created_at")
    raw_id_fields = ("post", "user")
    readonly_fields = ("created_at",)
    date_hierarchy = "day"
