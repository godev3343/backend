"""Refresh + Logout."""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView as SimpleJWTRefreshView

from apps.users.serializers import LogoutRequestSerializer

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer


@extend_schema(
    tags=["auth"],
    summary="Обновление access-токена",
    description=(
        "Принимает действующий refresh-токен и возвращает новый access. При "
        "включённой ротации refresh старый refresh попадает в blacklist, а в "
        "ответе приходит новый refresh — клиент должен сохранить его вместо "
        "прежнего.\n\n"
        "Возвращает 401, если refresh истёк, отозван или находится в blacklist."
    ),
    request=TokenRefreshSerializer,
    responses={
        200: TokenRefreshSerializer,
        401: DetailSerializer,
    },
)
class TokenRefreshView(SimpleJWTRefreshView):
    """Стандартный SimpleJWT view — указан явно для документации."""

    permission_classes = [AllowAny]


@extend_schema(
    tags=["auth"],
    summary="Логаут (отзыв refresh-токена)",
    description=(
        "Помещает переданный refresh-токен в blacklist, завершая сессию. "
        "Access-токен после этого продолжит работать до истечения своего "
        "короткого срока жизни — храните access недолго.\n\n"
        "Идемпотентно: если токен уже невалиден или в blacklist, всё равно "
        "возвращается 204."
    ),
    request=LogoutRequestSerializer,
    responses={204: None, 400: DetailSerializer, 401: DetailSerializer},
)
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
