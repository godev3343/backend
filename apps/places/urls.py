from __future__ import annotations

from django.urls import path

from apps.places.views import PlaceDetailView, PlaceListView

app_name = "places"

urlpatterns = [
    path("places/", PlaceListView.as_view(), name="list"),
    path("places/<int:pk>/", PlaceDetailView.as_view(), name="detail"),
]