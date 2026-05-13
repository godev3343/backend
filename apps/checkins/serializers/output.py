"""
Выходные сериализаторы для чек-инов.

Один CheckInSerializer покрывает три use-case:
- POST /api/checkins → возврат созданного.
- GET /api/checkins/me → история своих.
- GET /api/feed → лента друзей.

В фиде нужны user-publicname и is_liked. На /me юзер всегда сам, is_liked
не нужен. Делаем единый сериализатор с context-флагами, чтобы не дублировать
поля. Альтернатива (три отдельных класса) — DRY-нарушение без выигрыша.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.checkins.models import CheckIn


class CheckInPlaceMiniSerializer(serializers.Serializer):
    """Минимум данных о месте для рендера карточки в фиде."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()

    def get_lat(self, obj: Any) -> float:
        return obj.location.y

    def get_lng(self, obj: Any) -> float:
        return obj.location.x


class CheckInUserMiniSerializer(serializers.Serializer):
    """Публичный мини-профиль автора чек-ина."""

    id = serializers.IntegerField()
    public_name = serializers.CharField()
    avatar_url = serializers.SerializerMethodField()

    def get_avatar_url(self, obj: Any) -> str | None:
        asset = getattr(obj, "avatar_asset", None)
        if asset is None:
            return None
        # url_feed — стандартный публичный URL после processing.
        # Если status != PROCESSED, url_feed может вернуть None/original —
        # это ответственность MediaAsset, мы не лезем.
        return getattr(asset, "url_feed", None)


class CheckInSerializer(serializers.Serializer):
    """
    Универсальный сериализатор чек-ина.

    Поля:
      id, created_at, comment, likes_count — всегда.
      user — вложенный мини-профиль.
      place — вложенный мини-объект.
      lat/lng — координаты юзера в момент чек-ина (не места!).
      photo_url — feed-URL фото, если есть.
      is_liked — True/False/null. Заполняется только если context['liked_ids']
                 передан (set of checkin ids, лайкнутых текущим юзером).
                 Иначе остаётся null — клиент сам решит, не показывать состояние
                 или дозапросить.
    """

    id = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    comment = serializers.CharField()
    likes_count = serializers.IntegerField()
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()
    user = CheckInUserMiniSerializer()
    place = CheckInPlaceMiniSerializer()
    photo_url = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

    def get_lat(self, obj: CheckIn) -> float:
        return obj.location.y

    def get_lng(self, obj: CheckIn) -> float:
        return obj.location.x

    def get_photo_url(self, obj: CheckIn) -> str | None:
        if obj.photo_id is None:
            return None
        asset = getattr(obj.photo, "asset", None)
        if asset is None:
            return None
        return getattr(asset, "url_feed", None)

    def get_is_liked(self, obj: CheckIn) -> bool | None:
        liked_ids: set[int] | None = self.context.get("liked_ids")
        if liked_ids is None:
            return None
        return obj.id in liked_ids
