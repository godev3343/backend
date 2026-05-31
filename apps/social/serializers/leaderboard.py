"""Строка рейтинга. rank проставляется во view как атрибут на User-инстансе."""
from __future__ import annotations

from rest_framework import serializers

from apps.gamification.serializers.status import UserStatusSerializer


class LeaderboardRowSerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    id = serializers.IntegerField()
    display_name = serializers.CharField(source="public_name", read_only=True)
    avatar_url = serializers.URLField(allow_blank=True, allow_null=True)
    points = serializers.IntegerField()
    status = serializers.SerializerMethodField()

    def get_status(self, obj) -> dict:  # type: ignore[no-untyped-def]
        return UserStatusSerializer.for_points(obj.points)