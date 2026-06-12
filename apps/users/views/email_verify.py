"""Email verification request + confirm."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers import (
    EmailVerifyConfirmSerializer,
    EmailVerifyRequestSerializer,
)
from apps.users.services import AuthService
from apps.users.throttling import EmailVerifyRequestThrottle

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer


@extend_schema(
    tags=["auth"],
    summary="Запросить код верификации email",
    description=(
        "Отправляет 6-значный код подтверждения на указанный email. "
        "Ответ всегда 202 и одинаков независимо от того, существует ли аккаунт — "
        "так мы не раскрываем наличие email в системе (защита от перебора).\n\n"
        "Throttling по IP/email."
    ),
    request=EmailVerifyRequestSerializer,
    responses={202: DetailSerializer, 400: DetailSerializer, 429: DetailSerializer},
)
class EmailVerifyRequestView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [EmailVerifyRequestThrottle]

    def post(self, request: Request) -> Response:
        serializer = EmailVerifyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.request_email_verification(email=serializer.validated_data["email"])
        # Идемпотентный 202 — не палим существование email
        return Response(
            {"detail": "If the email exists, a verification code has been sent."},
            status=status.HTTP_202_ACCEPTED,
        )

@extend_schema(
    tags=["auth"],
    summary="Подтвердить email кодом",
    description=(
        "Подтверждает email по паре email + 6-значный код из письма. После "
        "успешного подтверждения аккаунт активируется и становится доступен "
        "логин.\n\n"
        "Возвращает 400, если код неверный или истёк."
    ),
    request=EmailVerifyConfirmSerializer,
    responses={200: DetailSerializer, 400: DetailSerializer},
)
class EmailVerifyConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = EmailVerifyConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.confirm_email_verification(**serializer.validated_data)
        return Response(
            {"detail": "Email verified successfully."},
            status=status.HTTP_200_OK,
        )
