"""Rate limit для /api/ai/recommend."""

from __future__ import annotations

from rest_framework.throttling import UserRateThrottle


class AiRecommendThrottle(UserRateThrottle):
    """10 запросов в час на юзера. Имя scope матчится с DEFAULT_THROTTLE_RATES."""

    scope = "ai_recommend"
