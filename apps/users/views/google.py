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

from apps.core.serializers import DetailSerializer, EmptySerializer


@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
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
