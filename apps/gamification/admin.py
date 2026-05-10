from django.contrib import admin

from apps.gamification.models import PointsTransaction


@admin.register(PointsTransaction)
class PointsTransactionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "delta", "reason", "ref_type", "ref_id", "created_at")
    list_filter = ("reason",)
    search_fields = ("user__username", "user__display_name")
    raw_id_fields = ("user",)
    readonly_fields = ("created_at",)