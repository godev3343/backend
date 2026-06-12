"""Health и readiness probes для Railway/k8s."""

from __future__ import annotations

from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.serializers import HealthSerializer, ReadinessSerializer


@extend_schema(
    tags=["system"],
    summary="Liveness probe",
    description=(
        "Проверка, что приложение запущено и отвечает. Намеренно не обращается "
        "к БД, кэшу или другим зависимостям — отвечает мгновенно (`{\"status\": "
        "\"ok\"}`) даже при недоступных зависимостях. Используется балансировщиком "
        "как liveness-проба."
    ),
    responses={200: HealthSerializer},
    auth=[],
)
class HealthView(APIView):
    """Liveness — приложение запущено и отвечает.

    КРИТИЧНО: не дёргает БД, кэш или что-либо ещё.
    Health должен отвечать мгновенно, даже если зависимости лежат.
    """

    serializer_class = HealthSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = ()  # ← throttle ходит в Redis, поэтому отключаем

    def get(self, request) -> Response:
        return Response({"status": "ok"})


@extend_schema(
    tags=["system"],
    summary="Readiness probe",
    description=(
        "Проверка доступности критичных зависимостей. БД — критична: при её "
        "недоступности статус `degraded` и код 503 (балансировщик не пускает "
        "трафик). Redis проверяется для наблюдаемости, но на статус не влияет.\n\n"
        "Возвращает `status` и пословный результат по каждой зависимости в "
        "`checks`."
    ),
    responses={
        200: inline_serializer(
            name="Readiness",
            fields={
                "status": serializers.CharField(),
                "checks": serializers.DictField(child=serializers.CharField()),
            },
        ),
        503: inline_serializer(
            name="ReadinessDegraded",
            fields={
                "status": serializers.CharField(),
                "checks": serializers.DictField(child=serializers.CharField()),
            },
        ),
    },
    auth=[],
)
class ReadinessView(APIView):
    """Readiness — критичные зависимости доступны.

    БД — критично (валит readiness, балансировщик не пускает трафик).
    Redis — observability only, не валит статус.
    """

    serializer_class = ReadinessSerializer
    permission_classes = (AllowAny,)
    authentication_classes = ()
    throttle_classes = ()

    def get(self, request) -> Response:
        checks: dict[str, str] = {}
        critical_ok = True

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            checks["database"] = "ok"
        except Exception as exc:
            checks["database"] = f"error: {exc}"
            critical_ok = False

        try:
            cache.set("readiness_probe", "1", timeout=5)
            cache.get("readiness_probe")
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"

        return Response(
            {"status": "ok" if critical_ok else "degraded", "checks": checks},
            status=status.HTTP_200_OK if critical_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        )