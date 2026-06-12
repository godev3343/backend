"""Google OAuth login."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers import (
    GoogleAuthRequestSerializer,
    GoogleAuthResponseSerializer,
)
from apps.users.services import GoogleAuthService
from apps.users.throttling import GoogleAuthRateThrottle

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer


@extend_schema(
    tags=["auth"],
    summary="Логин/регистрация через Google",
    description=(
        "Принимает Google ID-token (полученный на клиенте) и возвращает пару JWT "
        "(access + refresh). Если пользователя с этим Google-аккаунтом ещё нет — "
        "он создаётся, и в ответе `created=true`.\n\n"
        "Email из проверенного Google-аккаунта считается подтверждённым, "
        "отдельная верификация не нужна. Возвращает 401, если ID-token невалиден."
    ),
    request=GoogleAuthRequestSerializer,
    responses={
        200: GoogleAuthResponseSerializer,
        400: DetailSerializer,
        401: DetailSerializer,
        429: DetailSerializer,
    },
)
class GoogleAuthView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [GoogleAuthRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = GoogleAuthRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _, tokens, created = GoogleAuthService.authenticate(
            id_token=serializer.validated_data["id_token"]
        )
        return Response(
            GoogleAuthResponseSerializer(
                {
                    "access": tokens.access,
                    "refresh": tokens.refresh,
                    "created": created,
                }
            ).data,
            status=status.HTTP_200_OK,
        )
