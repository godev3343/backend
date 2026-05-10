from django.contrib.gis import admin as gis_admin

from apps.checkins.models import CheckIn


@gis_admin.register(CheckIn)
class CheckInAdmin(gis_admin.GISModelAdmin):
    list_display = ("id", "user", "place", "created_at")
    raw_id_fields = ("user", "place", "photo")
    readonly_fields = ("created_at",)
    date_hierarchy = "created_at"