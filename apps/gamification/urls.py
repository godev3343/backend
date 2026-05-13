"""URL-конфиг геймификации."""

from __future__ import annotations

from django.urls import path

from apps.gamification.views import MyPointsHistoryView

app_name = "gamification"

urlpatterns = [
    path("users/me/points", MyPointsHistoryView.as_view(), name="me-points"),
]
