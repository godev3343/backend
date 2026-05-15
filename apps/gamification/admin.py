from __future__ import annotations

from django.contrib import admin

from apps.gamification.models import (
    Achievement,
    PointsTransaction,
    UserAchievement,
)


@admin.register(PointsTransaction)
class PointsTransactionAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = (
        "id",
        "user",
        "delta",
        "reason",
        "ref_type",
        "ref_id",
        "created_at",
    )
    list_filter = ("reason",)
    search_fields = (
        "user__email",
        "user__first_name",
        "user__display_name",
    )
    raw_id_fields = ("user",)
    readonly_fields = ("created_at",)


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("code", "name_ru", "order")
    search_fields = ("code", "name_ru")
    ordering = ("order",)


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    list_display = ("id", "user", "achievement", "created_at")
    list_filter = ("achievement",)
    search_fields = ("user__email",)
    raw_id_fields = ("user", "achievement")
    readonly_fields = ("created_at",)