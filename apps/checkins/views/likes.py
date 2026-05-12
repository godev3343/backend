# apps/checkins/views/likes.py
"""POST/DELETE /api/checkins/{id}/like — лайк/анлайк."""
from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.checkins.services import LikeResult, LikeService


class CheckInLikeView(APIView):
    """
    POST /api/checkins/{id}/like:
      - первый лайк → 201
      - повторный → 200 (идемпотентно)
    DELETE /api/checkins/{id}/like:
      - лайк убран → 204
      - лайка не было → 204 (идемпотентно)

    В обоих случаях возвращаем актуальный likes_count, чтобы клиент мог
    обновить UI без отдельного запроса.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request: Request, pk: int) -> Response:
        result = LikeService.like(user=request.user, checkin_id=pk)
        status_code = (
            status.HTTP_201_CREATED
            if result == LikeResult.CREATED
            else status.HTTP_200_OK
        )
        return Response(
            self._payload(checkin_id=pk, is_liked=True),
            status=status_code,
        )

    def delete(self, request: Request, pk: int) -> Response:
        LikeService.unlike(user=request.user, checkin_id=pk)
        return Response(
            self._payload(checkin_id=pk, is_liked=False),
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _payload(*, checkin_id: int, is_liked: bool) -> dict:
        """
        Подтягиваем свежий likes_count из БД. Это +1 запрос, но даёт
        клиенту правду без race condition (несколько лайков в полёте).
        """
        from apps.checkins.models import CheckIn

        likes_count = (
            CheckIn.objects.filter(pk=checkin_id)
            .values_list("likes_count", flat=True)
            .first()
            or 0
        )
        return {
            "checkin_id": checkin_id,
            "is_liked": is_liked,
            "likes_count": likes_count,
        }