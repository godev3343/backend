"""Профиль и друзья."""
from __future__ import annotations

from django.urls import path

from apps.social.views import (
    FriendListView,
    FriendRemoveView,
    FriendRequestAcceptView,
    FriendRequestCancelView,
    FriendRequestCreateView,
    FriendRequestDeclineView,
    IncomingFriendRequestsView,
    OutgoingFriendRequestsView,
    UserMeView,
    UserPreferencesView,
    UserPublicView,
    UserSearchView,
)

app_name = "social"

urlpatterns = [
    # Profile
    path("users/me", UserMeView.as_view(), name="user_me"),
    path(
        "users/me/preferences",
        UserPreferencesView.as_view(),
        name="user_me_preferences",
    ),
    path("users/search", UserSearchView.as_view(), name="user_search"),
    path(
        "users/<int:user_id>",
        UserPublicView.as_view(),
        name="user_public",
    ),
    # Friend requests
    path(
        "friends/requests",
        FriendRequestCreateView.as_view(),
        name="friend_request_create",
    ),
    path(
        "friends/requests/incoming",
        IncomingFriendRequestsView.as_view(),
        name="friend_requests_incoming",
    ),
    path(
        "friends/requests/outgoing",
        OutgoingFriendRequestsView.as_view(),
        name="friend_requests_outgoing",
    ),
    path(
        "friends/requests/<int:friendship_id>/accept",
        FriendRequestAcceptView.as_view(),
        name="friend_request_accept",
    ),
    path(
        "friends/requests/<int:friendship_id>/decline",
        FriendRequestDeclineView.as_view(),
        name="friend_request_decline",
    ),
    path(
        "friends/requests/<int:friendship_id>",
        FriendRequestCancelView.as_view(),
        name="friend_request_cancel",
    ),
    # Friends
    path("friends", FriendListView.as_view(), name="friend_list"),
    path(
        "friends/<int:user_id>",
        FriendRemoveView.as_view(),
        name="friend_remove",
    ),
]