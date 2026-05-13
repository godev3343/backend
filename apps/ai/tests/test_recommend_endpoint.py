# apps/ai/tests/test_recommend_endpoint.py
"""E2E для POST /api/ai/recommend."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.ai.clients.base import LLMResponse
from apps.places.models import City
from apps.places.tests.factories import PlaceFactory


@pytest.mark.django_db
class TestAiRecommendEndpoint:
    def test_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        url = reverse("ai:recommend")
        resp = api_client.post(url, data={"query": "куда пойти"}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_not_onboarded_returns_403(self, authed_client: APIClient) -> None:
        # authed_client — юзер без display_name и consent_at
        url = reverse("ai:recommend")
        resp = authed_client.post(
            url, data={"query": "куда пойти"}, format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_short_query_rejected(self, onboarded_client: APIClient) -> None:
        url = reverse("ai:recommend")
        resp = onboarded_client.post(url, data={"query": "ab"}, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_happy_path(self, onboarded_client: APIClient, mocker) -> None:  # type: ignore[no-untyped-def]
        place = PlaceFactory(name="Test Place", is_verified=True, city=City.ASTANA)

        llm_resp = LLMResponse(
            text=json.dumps({
                "items": [{
                    "place_id": place.id,
                    "reasoning": "Подходит для тихой работы",
                    "vibe_match": ["calm"],
                }]
            }),
            input_tokens=500,
            output_tokens=50,
            model="gemini-2.5-flash",
        )
        client_mock = AsyncMock()
        client_mock.complete = AsyncMock(return_value=llm_resp)
        mocker.patch(
            "apps.ai.services.recommend.get_llm_client", return_value=client_mock
        )

        url = reverse("ai:recommend")
        resp = onboarded_client.post(
            url, data={"query": "куда пойти работать"}, format="json"
        )

        assert resp.status_code == status.HTTP_200_OK
        body = resp.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["place_id"] == place.id
        assert body["items"][0]["name"] == "Test Place"
        assert body["request_id"] > 0