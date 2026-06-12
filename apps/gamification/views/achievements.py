"""GET /api/users/me/achievements — список своих ачивок."""
from __future__ import annotations

from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.gamification.models import UserAchievement
from apps.gamification.serializers import UserAchievementSerializer

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer


@extend_schema(
    tags=["gamification"],
    summary="Мои ачивки",
    description=(
        "Все достижения, полученные текущим пользователем, с их определениями "
        "(название, описание, иконка) и временем получения. Отсортированы по "
        "порядку ачивок. Без пагинации — отдаётся плоским списком."
    ),
    responses={200: UserAchievementSerializer(many=True), 401: DetailSerializer},
)
class MyAchievementsView(ListAPIView):
    """
    GET /api/users/me/achievements

    Все ачивки, полученные текущим юзером.
    Без пагинации — ачивок мало (≤20 на pre-MVP), отдаём списком.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = UserAchievementSerializer
    pagination_class = None

    def get_queryset(self):  # type: ignore[no-untyped-def]
        if getattr(self, "swagger_fake_view", False):
            return UserAchievement.objects.none()
        return (
            UserAchievement.objects.filter(user=self.request.user)
            .select_related("achievement")
            .order_by("achievement__order", "id")
        )