"""Refresh + Logout."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as SimpleJWTRefreshView

from apps.users.serializers import LogoutRequestSerializer

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer, EmptySerializer


@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
class TokenRefreshView(SimpleJWTRefreshView):
    """Стандартный SimpleJWT view — указан явно для документации."""

    permission_classes = [AllowAny]


@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        serializer = LogoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            refresh = RefreshToken(serializer.validated_data["refresh"])
            refresh.blacklist()
        except TokenError:
            # Уже невалиден / blacklisted — для клиента это тот же успех
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)
