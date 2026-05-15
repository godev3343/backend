"""GET /api/users/me/achievements — список своих ачивок."""
from __future__ import annotations

from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from apps.gamification.models import UserAchievement
from apps.gamification.serializers import UserAchievementSerializer

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer, EmptySerializer


@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
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
        return (
            UserAchievement.objects.filter(user=self.request.user)
            .select_related("achievement")
            .order_by("achievement__order", "id")
        )