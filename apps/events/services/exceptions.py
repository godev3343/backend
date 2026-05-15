"""Доменные ошибки events-приложения."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class EventsError(DomainError):
    default_message = "Events error."
    default_code = "events_error"
    status_code = 400


class EventsInvalidBBox(EventsError):
    default_message = (
        "Invalid bbox. Expected 'lng_min,lat_min,lng_max,lat_max' "
        "with lng∈[-180,180], lat∈[-90,90], min<max."
    )
    default_code = "invalid_bbox"
    status_code = 400


class EventsBBoxTooLarge(EventsError):
    default_message = "BBox is too large. Zoom in."
    default_code = "bbox_too_large"
    status_code = 400


class InvalidPeriod(EventsError):
    default_message = "Invalid 'from'/'to' parameters."
    default_code = "invalid_period"
    status_code = 400


class EventNotFound(EventsError):
    default_message = "Event not found."
    default_code = "event_not_found"
    status_code = 404


class AttendanceEventNotFound(EventsError):
    default_message = "Event not found."
    default_code = "event_not_found"
    status_code = 404
