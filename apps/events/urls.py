from __future__ import annotations

from django.urls import path

from apps.events.views import EventDetailView, EventListView

app_name = "events"

urlpatterns = [
    path("events/", EventListView.as_view(), name="list"),
    path("events/<int:pk>/", EventDetailView.as_view(), name="detail"),
]
