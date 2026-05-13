"""Маршруты media: presign / confirm / asset detail."""

from __future__ import annotations

from django.urls import path

from apps.media.views import (
    ConfirmView,
    MediaAssetDetailView,
    PresignView,
)

app_name = "media"

urlpatterns = [
    path("upload/presign", PresignView.as_view(), name="upload_presign"),
    path("upload/confirm", ConfirmView.as_view(), name="upload_confirm"),
    path("media/<int:asset_id>", MediaAssetDetailView.as_view(), name="media_detail"),
]
