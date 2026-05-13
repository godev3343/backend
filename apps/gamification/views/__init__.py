"""Реэкспорт view-классов для urls.py."""
from apps.gamification.views.points_history import MyPointsHistoryView

__all__ = ["MyPointsHistoryView"]