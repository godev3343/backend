"""POST/DELETE/GET /api/events/{event_id}/attendance/ — кнопка "иду"."""

from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.events.serializers import EventAttendanceStateSerializer
from apps.events.services.attendance import AttendanceService
from apps.events.services.attendance_queries import friends_attending_qs
from apps.events.services.exceptions import AttendanceEventNotFound
from apps.users.permissions import IsEmailVerified, IsOnboarded

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer

# Максимум друзей, отдаваемый в attendance-endpoint.
# Полный список — отдельный endpoint /attendance/friends (TODO).
_FRIENDS_LIMIT = 20

_ATTENDANCE_RESPONSES = {
    200: EventAttendanceStateSerializer,
    401: DetailSerializer,
    403: DetailSerializer,
    404: DetailSerializer,
}


class EventAttendanceView(APIView):
    """
    GET    /api/events/{event_id}/attendance/   — состояние для текущего юзера
    POST   /api/events/{event_id}/attendance/   — отметить "иду"
    DELETE /api/events/{event_id}/attendance/   — отменить

    Permissions: IsEmailVerified + IsOnboarded — по аналогии с friends-flow.
    Анонимы видят счётчик через GET /api/events/{id} (там attendees_count в payload),
    но кнопка работает только после верификации и онбординга.
    """

    permission_classes = [IsAuthenticated, IsEmailVerified, IsOnboarded]

    @extend_schema(
        tags=["events"],
        summary="Состояние участия в событии",
        description=(
            "Возвращает для текущего пользователя: идёт ли он (`is_going`), общее "
            "число участников и превью друзей-участников. Требует подтверждённого "
            "email и онбординга. 404, если событие не найдено."
        ),
        responses=_ATTENDANCE_RESPONSES,
    )
    def get(self, request: Request, event_id: int) -> Response:
        # GET тоже проверяет существование, иначе фронт получает counts=0
        # и не понимает: ивент удалён или просто никто не идёт.
        self._ensure_event_exists(event_id)
        return Response(self._build_state(request.user, event_id))

    @extend_schema(
        tags=["events"],
        summary="Отметить «иду» на событие",
        description=(
            "Отмечает участие текущего пользователя в событии. Идемпотентно. "
            "Возвращает обновлённое состояние участия. Требует подтверждённого "
            "email и онбординга. 404, если событие не найдено."
        ),
        request=None,
        responses=_ATTENDANCE_RESPONSES,
    )
    def post(self, request: Request, event_id: int) -> Response:
        AttendanceService.mark_going(user=request.user, event_id=event_id)
        return Response(self._build_state(request.user, event_id))

    @extend_schema(
        tags=["events"],
        summary="Отменить участие в событии",
        description=(
            "Снимает отметку участия текущего пользователя. Идемпотентно. "
            "Возвращает обновлённое состояние участия. Требует подтверждённого "
            "email и онбординга. 404, если событие не найдено."
        ),
        responses=_ATTENDANCE_RESPONSES,
    )
    def delete(self, request: Request, event_id: int) -> Response:
        # mark_going бы упал на отсутствующем event, но cancel — нет
        # (на DELETE несуществующего ресурса тоже хочется 404, чтобы
        # клиент не считал отмену "успешной" на удалённом ивенте).
        self._ensure_event_exists(event_id)
        AttendanceService.cancel(user=request.user, event_id=event_id)
        return Response(self._build_state(request.user, event_id))

    # ---------- internals --------------------------------------------------

    @staticmethod
    def _ensure_event_exists(event_id: int) -> None:
        from apps.events.models import Event
        if not Event.objects.filter(pk=event_id).exists():
            raise AttendanceEventNotFound()

    @staticmethod
    def _build_state(user, event_id: int) -> dict:
        is_going = AttendanceService.is_going(user_id=user.pk, event_id=event_id)
        count = AttendanceService.count_for_event(event_id)
        friends = list(
            friends_attending_qs(viewer_id=user.pk, event_id=event_id)
            [:_FRIENDS_LIMIT]
        )

        return EventAttendanceStateSerializer({
            "is_going": is_going,
            "attendees_count": count,
            "friends_attending": friends,
        }).data