from django.contrib import admin
from django.contrib.gis import admin as gis_admin

from apps.checkins.models import CheckIn, Like


@gis_admin.register(CheckIn)
class CheckInAdmin(gis_admin.GISModelAdmin):
    list_display = ("id", "user", "place", "likes_count", "created_at")
    list_filter = ("place__category",)
    search_fields = ("user__email", "user__display_name", "place__name")
    raw_id_fields = ("user", "place", "photo")
    readonly_fields = ("created_at", "likes_count")
    date_hierarchy = "created_at"


@admin.register(Like)
class LikeAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "checkin", "created_at")
    search_fields = ("user__email", "user__display_name")
    raw_id_fields = ("user", "checkin")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"
