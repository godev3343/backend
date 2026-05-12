"""
Урезанный сериализатор чек-ина для блока recent_checkins в карточке места.

Не использует ModelSerializer от apps.checkins — публичный shape на странице
места не должен зависеть от модели CheckIn. EPIC 6 будет иметь свой
CheckInSerializer для /api/checkins/.
"""
from __future__ import annotations

from typing import Any

from rest_framework import serializers


class RecentCheckInSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    user_public_name = serializers.SerializerMethodField()
    comment = serializers.CharField()
    created_at = serializers.DateTimeField()

    def get_user_public_name(self, obj: Any) -> str:
        return obj.user.public_name