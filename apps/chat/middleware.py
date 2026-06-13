"""
JWT-аутентификация для WebSocket (Channels).

Токен берём из query (`?token=<access>`) либо из `Sec-WebSocket-Protocol`
(§3.1). Валидируем тем же SimpleJWT, что и REST. Невалидный/отсутствующий
токен → AnonymousUser; consumer закроет соединение.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

User = get_user_model()


@database_sync_to_async
def _user_from_token(raw_token: str) -> Any:
    # Импорты внутри — модели/JWT доступны только после django.setup().
    from rest_framework_simplejwt.exceptions import TokenError
    from rest_framework_simplejwt.tokens import AccessToken

    try:
        # AccessToken принимает str-токен; стаб типизирует его как Token|None.
        access = AccessToken(raw_token)  # type: ignore[arg-type]  # проверяет подпись/exp/тип
        user_id = access["user_id"]  # USER_ID_CLAIM из SIMPLE_JWT
    except (TokenError, KeyError):
        return AnonymousUser()

    try:
        return User.objects.get(pk=user_id, is_active=True)
    except User.DoesNotExist:
        return AnonymousUser()


def _extract_token(scope: dict[str, Any]) -> str | None:
    query = parse_qs(scope.get("query_string", b"").decode())
    if query.get("token"):
        return query["token"][0]
    for name, value in scope.get("headers", []):
        if name == b"sec-websocket-protocol":
            return value.decode().split(",")[0].strip()
    return None


class JWTAuthMiddleware:
    """ASGI-middleware: кладёт аутентифицированного юзера в scope['user']."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> Any:
        token = _extract_token(scope)
        scope["user"] = await _user_from_token(token) if token else AnonymousUser()
        return await self.inner(scope, receive, send)
