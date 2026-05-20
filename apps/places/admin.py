from django.contrib.gis import admin as gis_admin

from apps.places.models import Place, PlaceCategory, PlacePhoto, PlaceVibe

# Центр карты по умолчанию в Django GIS-админке — (0, 0), что визуально
# показывает Атлантику/Африку. Переопределяем на центр Астаны, чтобы при
# создании нового Place/Event/CheckIn карта сразу была в нужной точке.
# Используется через миксин ниже — реэкспортируется для events/checkins.
ASTANA_LAT = 51.1280
ASTANA_LON = 71.4307
ASTANA_ZOOM = 12


class AstanaCenteredGISAdmin(gis_admin.GISModelAdmin):
    """
    GISModelAdmin с центром в Астане. Применять везде, где модель имеет
    PointField и админ хочет видеть карту, центрированную на нашем городе.
    """

    gis_widget_kwargs = {
        "attrs": {
            "default_lat": ASTANA_LAT,
            "default_lon": ASTANA_LON,
            "default_zoom": ASTANA_ZOOM,
        },
    }


class PlaceVibeInline(gis_admin.TabularInline):
    model = PlaceVibe
    extra = 1


class PlacePhotoInline(gis_admin.TabularInline):
    model = PlacePhoto
    extra = 0
    fields = ("asset", "uploaded_by", "created_at")
    readonly_fields = ("created_at",)
    raw_id_fields = ("uploaded_by", "asset")


@gis_admin.register(Place)
class PlaceAdmin(AstanaCenteredGISAdmin):
    list_display = ("id", "name", "category", "is_verified", "address")
    list_filter = ("category", "is_verified")
    search_fields = ("name", "address")
    raw_id_fields = ("category",)
    inlines = [PlaceVibeInline, PlacePhotoInline]


@gis_admin.register(PlaceCategory)
class PlaceCategoryAdmin(gis_admin.ModelAdmin):
    list_display = ("slug", "name_ru", "name_kk")
    search_fields = ("name_ru", "slug")


@gis_admin.register(PlacePhoto)
class PlacePhotoAdmin(gis_admin.ModelAdmin):
    list_display = ("id", "place", "uploaded_by", "created_at")
    raw_id_fields = ("place", "uploaded_by")
    readonly_fields = ("created_at",)