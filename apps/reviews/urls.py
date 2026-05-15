from __future__ import annotations

from django.urls import path

from apps.reviews.views import (
    PlaceReviewsView,
    ReviewDetailView,
    ReviewLikeView,
)

app_name = "reviews"

urlpatterns = [
    path(
        "places/<int:place_id>/reviews",
        PlaceReviewsView.as_view(),
        name="place-reviews",
    ),
    path(
        "reviews/<int:pk>",
        ReviewDetailView.as_view(),
        name="detail",
    ),
    path(
        "reviews/<int:pk>/like",
        ReviewLikeView.as_view(),
        name="like",
    ),
]