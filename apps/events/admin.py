from django.contrib.gis import admin as gis_admin

from apps.events.models import Event


@gis_admin.register(Event)
class EventAdmin(gis_admin.GISModelAdmin):
    list_display = ("id", "title", "place", "starts_at", "ends_at")
    list_filter = ("starts_at",)
    search_fields = ("title", "description")
    # autocomplete работает благодаря PlaceAdmin.search_fields = ("name", "address").
    # Если place задан — location в save() будет перезатёрт place.location,
    # поэтому widget для location уместен только когда place пуст.
    autocomplete_fields = ("place",)
    raw_id_fields = ("created_by",)
    date_hierarchy = "starts_at"
    fieldsets = (
        (None, {"fields": ("title", "description", "cover_url")}),
        (
            "Расположение",
            {
                "fields": ("place", "location"),
                "description": (
                    "Укажите либо место (тогда координаты возьмутся из него), "
                    "либо точку на карте. Должно быть задано хотя бы одно."
                ),
            },
        ),
        ("Время", {"fields": ("starts_at", "ends_at")}),
        ("Служебное", {"fields": ("created_by",)}),
    )
