"""Register + Login."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.users.serializers import (
    LoginRequestSerializer,
    RegisterRequestSerializer,
    TokenPairResponseSerializer,
)
from apps.users.services import AuthService
from apps.users.throttling import LoginRateThrottle, RegisterRateThrottle

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer


@extend_schema(
    tags=["auth"],
    summary="Регистрация по email",
    description=(
        "Создаёт пользователя по email + паролю и отправляет 6-значный код "
        "верификации на почту. Аккаунт создаётся неподтверждённым: чтобы войти, "
        "сначала подтвердите email через `POST /api/auth/email/verify/confirm`.\n\n"
        "Пароль проходит валидаторы Django (минимум 8 символов, не слишком "
        "простой). Throttling по IP."
    ),
    request=RegisterRequestSerializer,
    responses={
        201: DetailSerializer,
        400: DetailSerializer,
        429: DetailSerializer,
    },
)
class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [RegisterRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = RegisterRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        AuthService.register(**serializer.validated_data)
        return Response(
            {
                "detail": ("Registration successful. Check your email for verification code."),
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(
    tags=["auth"],
    summary="Логин по email и паролю",
    description=(
        "Аутентифицирует пользователя по email + паролю и возвращает пару JWT "
        "(access + refresh). Access кладётся в заголовок `Authorization: Bearer "
        "<access>`, refresh используется для продления сессии через "
        "`POST /api/auth/token/refresh`.\n\n"
        "Логин невозможен, пока email не подтверждён. Throttling по IP."
    ),
    request=LoginRequestSerializer,
    responses={
        200: TokenPairResponseSerializer,
        400: DetailSerializer,
        401: DetailSerializer,
        429: DetailSerializer,
    },
)
class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request: Request) -> Response:
        serializer = LoginRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = AuthService.login(**serializer.validated_data)
        return Response(
            TokenPairResponseSerializer({"access": tokens.access, "refresh": tokens.refresh}).data,
            status=status.HTTP_200_OK,
        )
