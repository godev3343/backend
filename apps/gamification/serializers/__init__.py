# apps/gamification/serializers/__init__.py
"""Реэкспорт сериализаторов."""
from apps.gamification.serializers.points_history import (
    PointsTransactionSerializer,
)

__all__ = ["PointsTransactionSerializer"]