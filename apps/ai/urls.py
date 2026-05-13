# apps/ai/urls.py
"""AI endpoints."""
from __future__ import annotations

from django.urls import path

from apps.ai.views import AiRecommendView

app_name = "ai"

urlpatterns = [
    path("ai/recommend", AiRecommendView.as_view(), name="recommend"),
]