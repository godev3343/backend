"""URL-конфиг геймификации."""

from __future__ import annotations

from django.urls import path

from apps.gamification.views import MyAchievementsView, MyPointsHistoryView

app_name = "gamification"

urlpatterns = [
    path("users/me/points", MyPointsHistoryView.as_view(), name="me-points"),
    path(
        "users/me/achievements",
        MyAchievementsView.as_view(),
        name="me-achievements",
    ),
]
