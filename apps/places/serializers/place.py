"""Сериализаторы Place: компактный list-item и полная карточка detail."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.media.models import MediaAsset, MediaStatus
from apps.places.models import Place
from apps.places.serializers.category import PlaceCategorySerializer
from apps.places.serializers.checkin import RecentCheckInSerializer
from apps.places.serializers.photo import PlacePhotoSerializer
from apps.places.serializers.vibe import PlaceVibeSerializer


class PlaceListItemSerializer(serializers.Serializer):
    """
    Маркер на карте. Отдаём минимум, всё необходимое для рендера пина
    и быстрого preview без второго запроса.

    NB: НЕ возвращаем geometry-объект через GeoFeatureSerializer.
    Маркерам нужны просто lat/lng как числа — клиент сам собирает GeoJSON,
    если надо. Это в разы дешевле по байтам и парсингу.
    """

    id = serializers.IntegerField()
    name = serializers.CharField()
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()
    category_slug = serializers.CharField(source="category.slug")
    primary_vibe = serializers.CharField(source="primary_vibe_tag", default=None, allow_null=True)
    thumb_url = serializers.SerializerMethodField()

    def get_lat(self, obj: Place) -> float:
        return obj.location.y

    def get_lng(self, obj: Place) -> float:
        return obj.location.x

    def get_thumb_url(self, obj: Place) -> str | None:
        """
        thumb_asset_id аннотирован в build_list_queryset.
        Если None — у места нет PROCESSED-фото, отдаём null (фронт ставит placeholder).
        """
        asset_id = getattr(obj, "thumb_asset_id", None)
        if asset_id is None:
            return None
        # context['thumb_assets_by_id'] — preloaded map, чтобы не тащить
        # MediaAsset на каждую строку (см. PlaceListView).
        assets_map: dict[int, MediaAsset] = self.context.get("thumb_assets_by_id", {})
        asset = assets_map.get(asset_id)
        return asset.url_thumb if asset else None


class PlaceDetailSerializer(serializers.ModelSerializer):
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()
    category = PlaceCategorySerializer(read_only=True)
    vibes = serializers.SerializerMethodField()
    photos = serializers.SerializerMethodField()
    recent_checkins = serializers.SerializerMethodField()

    class Meta:
        model = Place
        fields = (
            "id",
            "name",
            "lat",
            "lng",
            "address",
            "phone",
            "hours_json",
            "description",
            "is_verified",
            "category",
            "vibes",
            "photos",
            "recent_checkins",
        )

    def get_lat(self, obj: Place) -> float:
        return obj.location.y

    def get_lng(self, obj: Place) -> float:
        return obj.location.x

    def get_vibes(self, obj: Place) -> list[dict[str, Any]]:
        # vibes prefetched в view; сортируем по weight desc для UX.
        vibes = sorted(obj.vibes.all(), key=lambda v: v.weight, reverse=True)
        return PlaceVibeSerializer(vibes, many=True).data

    def get_photos(self, obj: Place) -> list[dict[str, Any]]:
        # Только PROCESSED — фильтр в Python, потому что photos prefetched.
        # Это дешевле чем второй query + filter.
        ready_photos = [
            p for p in obj.photos.all() if p.asset_id and p.asset.status == MediaStatus.PROCESSED
        ]
        ready_photos.sort(key=lambda p: (p.created_at, p.id), reverse=True)
        return PlacePhotoSerializer(ready_photos, many=True).data

    def get_recent_checkins(self, obj: Place) -> list[dict[str, Any]]:
        # _recent_checkins аттач'ится в PlaceDetailView отдельным запросом
        recent = getattr(obj, "_recent_checkins", [])
        return RecentCheckInSerializer(recent, many=True).data
