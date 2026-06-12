"""Password reset request + confirm."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers import (
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
)
from apps.users.services import AuthService
from apps.users.throttling import PasswordResetRequestThrottle

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer


@extend_schema(
    tags=["auth"],
    summary="Запросить сброс пароля",
    description=(
        "Отправляет на email ссылку/токен для сброса пароля. Ответ всегда 202 и "
        "не зависит от существования аккаунта — наличие email не раскрывается.\n\n"
        "Throttling по IP/email."
    ),
    request=PasswordResetRequestSerializer,
    responses={202: DetailSerializer, 400: DetailSerializer, 429: DetailSerializer},
)
class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRequestThrottle]

    def post(self, request: Request) -> Response:
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.request_password_reset(email=serializer.validated_data["email"])
        return Response(
            {"detail": "If the email exists, a reset link has been sent."},
            status=status.HTTP_202_ACCEPTED,
        )


@extend_schema(
    tags=["auth"],
    summary="Подтвердить сброс пароля",
    description=(
        "Устанавливает новый пароль по токену из письма. Новый пароль проходит "
        "валидаторы Django (минимум 8 символов, не слишком простой).\n\n"
        "Возвращает 400, если токен неверный, истёк или пароль не прошёл "
        "валидацию."
    ),
    request=PasswordResetConfirmSerializer,
    responses={200: DetailSerializer, 400: DetailSerializer},
)
class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.confirm_password_reset(**serializer.validated_data)
        return Response(
            {"detail": "Password has been reset."},
            status=status.HTTP_200_OK,
        )
