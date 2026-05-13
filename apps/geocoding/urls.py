from __future__ import annotations

from django.urls import path

from apps.geocoding.views import GeocodeView

app_name = "geocoding"

urlpatterns = [
    path("geocode/", GeocodeView.as_view(), name="forward"),
]
