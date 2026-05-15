from __future__ import annotations

from django.urls import path

from apps.events.views import (
    EventAttendanceView,
    EventDetailView,
    EventListView,
)

app_name = "events"

urlpatterns = [
    path("events/", EventListView.as_view(), name="list"),
    path("events/<int:pk>/", EventDetailView.as_view(), name="detail"),
    path(
        "events/<int:event_id>/attendance/",
        EventAttendanceView.as_view(),
        name="attendance",
    ),
]
