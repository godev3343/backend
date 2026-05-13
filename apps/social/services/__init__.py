"""Реэкспорт сервисов social-домена."""

from apps.social.services.friendship import FriendshipService
from apps.social.services.queries import annotate_friendship_status

__all__ = ["FriendshipService", "annotate_friendship_status"]
