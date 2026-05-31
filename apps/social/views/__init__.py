"""Реэкспорт view-классов для urls.py."""

from apps.social.views.friends import (
    FriendListView,
    FriendRemoveView,
    FriendRequestAcceptView,
    FriendRequestCancelView,
    FriendRequestCreateView,
    FriendRequestDeclineView,
    IncomingFriendRequestsView,
    OutgoingFriendRequestsView,
)
from apps.social.views.preferences import (
    UserPreferencesView,
)
from apps.social.views.user import (
    UserMeView,
    UserPublicView,
    UserSearchView,
)
from apps.social.views.leaderboard import (
    FriendsLeaderboardView,
    GlobalLeaderboardView,
)

__all__ = [
    "FriendListView",
    "FriendRemoveView",
    "FriendRequestAcceptView",
    "FriendRequestCancelView",
    "FriendRequestCreateView",
    "FriendRequestDeclineView",
    "IncomingFriendRequestsView",
    "OutgoingFriendRequestsView",
    "UserMeView",
    "UserPreferencesView",
    "UserPublicView",
    "UserSearchView",
    "FriendsLeaderboardView",
    "GlobalLeaderboardView",
]
