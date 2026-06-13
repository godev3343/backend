"""WebSocket-маршруты чата. Импортируется в config/asgi.py после django.setup()."""

from __future__ import annotations

from django.urls import path

from apps.chat.consumers import ChatConsumer

websocket_urlpatterns = [
    path("ws/chat", ChatConsumer.as_asgi()),
]
