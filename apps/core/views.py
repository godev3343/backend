"""Health и readiness probes для Railway/k8s."""
from __future__ import annotations

from django.core.cache import cache
from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness — приложение запущено и отвечает."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request) -> Response:
        return Response({"status": "ok"})


class ReadinessView(APIView):
    """Readiness — БД и Redis доступны.

    Используется балансировщиком: если возвращает 503, трафик не пускается.
    """

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def get(self, request) -> Response:
        checks: dict[str, str] = {}

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            checks["database"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["database"] = f"error: {exc}"

        try:
            cache.set("readiness_probe", "1", timeout=5)
            cache.get("readiness_probe")
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            checks["redis"] = f"error: {exc}"

        all_ok = all(v == "ok" for v in checks.values())
        return Response(
            {"status": "ok" if all_ok else "degraded", "checks": checks},
            status=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )