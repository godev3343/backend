"""Тесты геокодинг-эндпоинта и сервиса."""
from __future__ import annotations

import pytest
import respx
from django.urls import reverse
from httpx import Response

from apps.geocoding.services.exceptions import (
    GeocodingNotConfigured,
    GeocodingUpstreamError,
    InvalidGeocodingQuery,
)
from apps.geocoding.services.geocoder import geocode
from apps.geocoding.services.mapbox import MAPBOX_FORWARD_URL


@pytest.fixture
def mapbox_response_ok() -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "id": "address.1",
                "geometry": {"type": "Point", "coordinates": [71.42, 51.09]},
                "properties": {
                    "name": "Кенесары 10",
                    "full_address": "ул. Кенесары 10, Астана, Казахстан",
                    "feature_type": "address",
                },
            },
            {
                "id": "address.2",
                "geometry": {"type": "Point", "coordinates": [71.43, 51.10]},
                "properties": {
                    "name": "Кенесары 12",
                    "full_address": "ул. Кенесары 12, Астана, Казахстан",
                    "feature_type": "address",
                },
            },
        ],
    }


class TestGeocodeService:
    @respx.mock
    def test_returns_normalized_results(
        self, settings, mapbox_response_ok
    ) -> None:
        settings.MAPBOX_ACCESS_TOKEN = "fake-token"

        respx.get(MAPBOX_FORWARD_URL).mock(
            return_value=Response(200, json=mapbox_response_ok)
        )

        results = geocode("Кенесары 10")
        assert len(results) == 2
        assert results[0].name == "ул. Кенесары 10, Астана, Казахстан"
        assert results[0].lat == pytest.approx(51.09)
        assert results[0].lng == pytest.approx(71.42)
        assert results[0].place_type == "address"

    @respx.mock
    def test_cached_on_second_call(self, settings, mapbox_response_ok) -> None:
        settings.MAPBOX_ACCESS_TOKEN = "fake-token"

        route = respx.get(MAPBOX_FORWARD_URL).mock(
            return_value=Response(200, json=mapbox_response_ok)
        )

        geocode("Кенесары 10")
        geocode("Кенесары 10")

        assert route.call_count == 1

    @respx.mock
    def test_normalization_hits_same_cache(
        self, settings, mapbox_response_ok
    ) -> None:
        settings.MAPBOX_ACCESS_TOKEN = "fake-token"

        route = respx.get(MAPBOX_FORWARD_URL).mock(
            return_value=Response(200, json=mapbox_response_ok)
        )

        geocode("Кенесары 10")
        geocode("  кенесары  10  ")  # whitespace + case
        assert route.call_count == 1

    def test_empty_query_400(self, settings) -> None:
        settings.MAPBOX_ACCESS_TOKEN = "fake-token"
        with pytest.raises(InvalidGeocodingQuery):
            geocode("")

    def test_too_short_query_400(self, settings) -> None:
        settings.MAPBOX_ACCESS_TOKEN = "fake-token"
        with pytest.raises(InvalidGeocodingQuery):
            geocode("a")

    def test_no_token_503(self, settings) -> None:
        settings.MAPBOX_ACCESS_TOKEN = ""
        with pytest.raises(GeocodingNotConfigured):
            geocode("Кенесары 10")

    @respx.mock
    def test_upstream_5xx_502(self, settings) -> None:
        settings.MAPBOX_ACCESS_TOKEN = "fake-token"
        respx.get(MAPBOX_FORWARD_URL).mock(return_value=Response(503))
        with pytest.raises(GeocodingUpstreamError):
            geocode("Кенесары 10")

    @respx.mock
    def test_upstream_invalid_json_502(self, settings) -> None:
        settings.MAPBOX_ACCESS_TOKEN = "fake-token"
        respx.get(MAPBOX_FORWARD_URL).mock(
            return_value=Response(200, text="not json")
        )
        with pytest.raises(GeocodingUpstreamError):
            geocode("Кенесары 10")

    @respx.mock
    def test_broken_feature_skipped(self, settings) -> None:
        settings.MAPBOX_ACCESS_TOKEN = "fake-token"
        respx.get(MAPBOX_FORWARD_URL).mock(
            return_value=Response(
                200,
                json={
                    "features": [
                        {"id": "bad", "geometry": {}, "properties": {}},
                        {
                            "id": "ok",
                            "geometry": {"coordinates": [71.0, 51.0]},
                            "properties": {"full_address": "addr"},
                        },
                    ]
                },
            )
        )
        results = geocode("Кенесары 10")
        assert len(results) == 1
        assert results[0].id == "ok"


@pytest.mark.django_db
class TestGeocodeView:
    @respx.mock
    def test_requires_auth(self, api_client, settings, mapbox_response_ok) -> None:
        settings.MAPBOX_ACCESS_TOKEN = "fake-token"
        api_client.credentials()
        url = reverse("geocoding:forward")
        resp = api_client.get(url, {"q": "Кенесары 10"})
        assert resp.status_code == 401

    @respx.mock
    def test_returns_results(
        self, authed_client, settings, mapbox_response_ok
    ) -> None:
        settings.MAPBOX_ACCESS_TOKEN = "fake-token"
        respx.get(MAPBOX_FORWARD_URL).mock(
            return_value=Response(200, json=mapbox_response_ok)
        )
        url = reverse("geocoding:forward")
        resp = authed_client.get(url, {"q": "Кенесары 10"})
        assert resp.status_code == 200
        assert len(resp.data["results"]) == 2
        first = resp.data["results"][0]
        assert {"id", "name", "lat", "lng", "place_type"} <= first.keys()

    def test_missing_q_400(self, authed_client) -> None:
        url = reverse("geocoding:forward")
        resp = authed_client.get(url)
        assert resp.status_code == 400
        assert resp.data["code"] == "invalid_query"