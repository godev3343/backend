"""
PUT /api/users/me/preferences — атомарная замена AI-настроек.

Семантика: полная замена preferred_vibes + ai_context. Отдельный
эндпоинт от PATCH /me, чтобы фронт онбординга мог использовать PUT
(идемпотентно по smtp-ретраю) и не следить за тем, какие поля прислал.
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.social.serializers import UserPreferencesSerializer

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer


@extend_schema(
    tags=["social"],
    summary="Заменить AI-предпочтения",
    description=(
        "Идемпотентная полная замена AI-настроек: `preferred_vibes` (0–5 "
        "уникальных тегов вайба) и `ai_context` (свободный текст до 500 "
        "символов). В отличие от частичного `PATCH /api/users/me`, оба поля "
        "обязательны — это «новое состояние целиком».\n\n"
        "Используется в онбординге и на экране «AI-предпочтения». Возвращает "
        "сохранённые значения."
    ),
    request=UserPreferencesSerializer,
    responses={200: UserPreferencesSerializer, 400: DetailSerializer, 401: DetailSerializer},
)
class UserPreferencesView(APIView):
    """PUT /api/users/me/preferences."""

    permission_classes = [IsAuthenticated]

    def put(self, request: Request) -> Response:
        serializer = UserPreferencesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user
        user.preferred_vibes = data["preferred_vibes"]
        user.ai_context = data["ai_context"]
        user.save(update_fields=["preferred_vibes", "ai_context"])

        return Response(
            {
                "preferred_vibes": user.preferred_vibes,
                "ai_context": user.ai_context,
            },
            status=status.HTTP_200_OK,
        )
