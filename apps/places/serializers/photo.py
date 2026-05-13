"""Сериализатор фотографии места."""

from __future__ import annotations

from rest_framework import serializers

from apps.places.models import PlacePhoto


class PlacePhotoSerializer(serializers.Serializer):
    """
    Только готовые (PROCESSED) фото попадают в карточку — клиенту
    не нужно знать про in-progress загрузки.
    """

    id = serializers.IntegerField()
    feed_url = serializers.SerializerMethodField()
    thumb_url = serializers.SerializerMethodField()
    width = serializers.IntegerField(source="asset.width")
    height = serializers.IntegerField(source="asset.height")
    created_at = serializers.DateTimeField()

    def get_feed_url(self, obj: PlacePhoto) -> str:
        return obj.asset.url_feed

    def get_thumb_url(self, obj: PlacePhoto) -> str:
        return obj.asset.url_thumb
