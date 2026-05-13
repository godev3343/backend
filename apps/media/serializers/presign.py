"""Сериализаторы для POST /api/upload/presign."""
from __future__ import annotations

from rest_framework import serializers

from apps.media.models import MediaPurpose
from apps.media.services.keys import CONTENT_TYPE_TO_EXT


class PresignRequestSerializer(serializers.Serializer):
    """
    Тело запроса presign.

    purpose — что юзер загружает (avatar/checkin/place). Влияет на лимит.
    content_type — MIME для подписи. Клиент обязан использовать ровно его
                   в PUT-запросе, иначе R2 отвергнет.
    content_length — точный размер. Тоже подписывается, нельзя загрузить
                     больше / меньше заявленного.
    """

    purpose = serializers.ChoiceField(choices=MediaPurpose.choices)
    content_type = serializers.ChoiceField(choices=sorted(CONTENT_TYPE_TO_EXT.keys()))
    content_length = serializers.IntegerField(min_value=1)


class PresignResponseSerializer(serializers.Serializer):
    """Ответ presign. Используется только для OpenAPI-схемы."""

    asset_id = serializers.IntegerField()
    upload_url = serializers.URLField()
    key = serializers.CharField()
    expires_in = serializers.IntegerField()