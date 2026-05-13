"""Сериализатор для GET /api/users/me/points."""

from __future__ import annotations

from rest_framework import serializers

from apps.gamification.models import PointsTransaction


class PointsTransactionSerializer(serializers.ModelSerializer):
    """Запись истории начисления."""

    class Meta:
        model = PointsTransaction
        fields = ("id", "delta", "reason", "ref_type", "ref_id", "created_at")
        read_only_fields = fields
