"""GET /api/users/me/points — история начислений текущего юзера."""

from __future__ import annotations

from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.gamification.models import PointsTransaction
from apps.gamification.pagination import PointsHistoryCursorPagination
from apps.gamification.serializers import PointsTransactionSerializer

from drf_spectacular.utils import extend_schema


@extend_schema(
    tags=["gamification"],
    summary="История начисления поинтов",
    description=(
        "История транзакций поинтов текущего пользователя в обратном "
        "хронологическом порядке: величина (`delta`), причина и ссылка на "
        "источник (`ref_type`/`ref_id`). Cursor-пагинация по 50 записей.\n\n"
        "Онбординг не требуется — историю можно смотреть, даже если что-то уже "
        "начислено до его завершения."
    ),
)
class MyPointsHistoryView(ListAPIView):
    """
    GET /api/users/me/points

    Возвращает историю начислений текущего юзера, отсортированную по
    created_at DESC. Cursor-пагинация по 50 на страницу.

    Permissions: IsAuthenticated. НЕ требуем IsOnboarded — историю можно
    смотреть и до завершения онбординга (если что-то уже начислено).
    """

    permission_classes = (IsAuthenticated,)
    pagination_class = PointsHistoryCursorPagination
    serializer_class = PointsTransactionSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        if getattr(self, "swagger_fake_view", False):
            return PointsTransaction.objects.none()
        return PointsTransaction.objects.filter(user=self.request.user).order_by(
            "-created_at", "-id"
        )
