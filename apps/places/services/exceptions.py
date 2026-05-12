"""Доменные ошибки places-приложения."""
from __future__ import annotations

from apps.core.exceptions import DomainError


class PlacesError(DomainError):
    default_message = "Places error."
    default_code = "places_error"
    status_code = 400


class InvalidBBox(PlacesError):
    default_message = (
        "Invalid bbox. Expected 'lng_min,lat_min,lng_max,lat_max' "
        "with lng∈[-180,180], lat∈[-90,90], min<max."
    )
    default_code = "invalid_bbox"
    status_code = 400


class BBoxTooLarge(PlacesError):
    default_message = "BBox is too large. Zoom in."
    default_code = "bbox_too_large"
    status_code = 400


class InvalidVibe(PlacesError):
    default_message = "Unknown vibe tag."
    default_code = "invalid_vibe"
    status_code = 400


class PlaceNotFound(PlacesError):
    default_message = "Place not found."
    default_code = "place_not_found"
    status_code = 404