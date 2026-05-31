"""
Рейтинги по поинтам.

Решения:
- select_related('avatar_asset') обязателен: User.avatar_url — property через
  avatar_asset.url_feed, без него N+1 на каждой строке.
- Сортировка '-points', 'pk': pk как стабильный tiebreak, иначе offset-пагинация
  может «прыгать» при равных поинтах.
- Друзья-рейтинг включает самого юзера (видеть своё место среди друзей).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db.models import QuerySet

from apps.social.services.friendship import FriendshipService

if TYPE_CHECKING:
    from apps.users.models import User as UserType

User = get_user_model()


class LeaderboardService:
    """Stateless — все методы classmethod/staticmethod."""

    @staticmethod
    def _base_qs() -> QuerySet:
        return (
            User.objects.filter(is_active=True)
            .select_related("avatar_asset")
            .order_by("-points", "pk")
        )

    @classmethod
    def global_qs(cls) -> QuerySet:
        """Все активные юзеры по убыванию поинтов."""
        return cls._base_qs()

    @classmethod
    def friends_qs(cls, *, user: UserType) -> QuerySet:
        """Сам юзер + друзья (accepted в обе стороны) по убыванию поинтов."""
        friend_ids = set(
            FriendshipService.list_friends(user=user).values_list("pk", flat=True)
        )
        friend_ids.add(user.pk)
        return cls._base_qs().filter(pk__in=friend_ids)