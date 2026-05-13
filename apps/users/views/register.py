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
