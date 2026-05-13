"""POST /api/ai/recommend — рекомендации "Куда пойти?"."""
from __future__ import annotations

from asgiref.sync import async_to_sync
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.serializers import (
    AiRecommendRequestSerializer,
    AiRecommendResponseSerializer,
)
from apps.ai.services.recommend import recommend
from apps.ai.throttling import AiRecommendThrottle
from apps.users.permissions import IsOnboarded


class AiRecommendView(APIView):
    """
    POST /api/ai/recommend
    body: {"query": "куда пойти на свидание?"}
    response: {"items": [...], "request_id": 42}

    Onboarded-only — без preferred_vibes/ai_context AI знает только город,
    рекомендации будут слабыми. Throttle: 10/час на юзера (см. throttling.py).
    """

    permission_classes = [IsAuthenticated, IsOnboarded]
    throttle_classes = [AiRecommendThrottle]

    def post(self, request: Request) -> Response:
        ser = AiRecommendRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        query = ser.validated_data["query"]

        # recommend() — async; DRF view sync. async_to_sync создаёт event loop
        # на одну операцию. Оверхед копеечный относительно 1-5 сек LLM-вызова.
        result = async_to_sync(recommend)(user_id=request.user.pk, query=query)

        payload = {
            "items": [
                {
                    "place_id": r.place_id,
                    "name": r.name,
                    "reasoning": r.reasoning,
                    "vibe_match": r.vibe_match,
                }
                for r in result.items
            ],
            "request_id": result.log_id,
        }
        return Response(
            AiRecommendResponseSerializer(payload).data,
            status=status.HTTP_200_OK,
        )