"""Реэкспорт view-классов для urls.py."""

from apps.ai.views.recommend import AiRecommendView

__all__ = [
    "AiRecommendView",
]
