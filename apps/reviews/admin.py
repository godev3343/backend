from __future__ import annotations

from django.contrib import admin

from apps.reviews.models import Review, ReviewLike


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("id", "user", "place", "rating", "likes_count", "created_at")
    list_filter = ("rating",)
    search_fields = ("user__email", "place__name", "text")
    raw_id_fields = ("user", "place", "photo")
    readonly_fields = ("likes_count", "created_at", "updated_at")


@admin.register(ReviewLike)
class ReviewLikeAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("id", "user", "review", "created_at")
    raw_id_fields = ("user", "review")
    readonly_fields = ("created_at",)