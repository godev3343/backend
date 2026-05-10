from django.contrib.gis import admin as gis_admin

from apps.events.models import Event


@gis_admin.register(Event)
class EventAdmin(gis_admin.GISModelAdmin):
    list_display = ("id", "title", "place", "starts_at", "ends_at")
    list_filter = ("starts_at",)
    search_fields = ("title", "description")
    raw_id_fields = ("place", "created_by")
    date_hierarchy = "starts_at"