from __future__ import annotations

from django.urls import path

from apps.checkins.views import (
    CheckInCreateView,
    CheckInLikeView,
    FeedView,
    MyCheckInsView,
)

app_name = "checkins"

urlpatterns = [
    path("checkins/", CheckInCreateView.as_view(), name="create"),
    path("checkins/me/", MyCheckInsView.as_view(), name="me"),
    path("checkins/<int:pk>/like/", CheckInLikeView.as_view(), name="like"),
    path("feed/", FeedView.as_view(), name="feed"),
]