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

from apps.core.serializers import DetailSerializer, EmptySerializer

@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
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

@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
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
