"""Сериализаторы для POST /api/upload/confirm."""
from __future__ import annotations

from rest_framework import serializers


class ConfirmRequestSerializer(serializers.Serializer):
    asset_id = serializers.IntegerField(min_value=1)


class MediaAssetSerializer(serializers.Serializer):
    """
    Презентация MediaAsset для клиента.

    URL'ы отдаём готовыми — фронт не должен знать про R2_PUBLIC_URL.
    Для PENDING/FAILED url_feed/thumb равны url_original (через property
    в модели).
    """

    id = serializers.IntegerField()
    purpose = serializers.CharField()
    status = serializers.CharField()
    failure_reason = serializers.CharField(allow_blank=True)
    url_original = serializers.CharField()
    url_feed = serializers.CharField()
    url_thumb = serializers.CharField()
    width = serializers.IntegerField()
    height = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    processed_at = serializers.DateTimeField(allow_null=True)