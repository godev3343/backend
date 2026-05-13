"""Ошибки friendship-домена. Наследуются от DomainError (НЕ от APIException)."""

from __future__ import annotations

from apps.core.exceptions import DomainError


class FriendshipError(DomainError):
    default_message = "Friendship error."
    default_code = "friendship_error"
    status_code = 400


class SelfFriendshipError(FriendshipError):
    default_message = "Cannot send friend request to yourself."
    default_code = "self_friendship"
    status_code = 400


class FriendshipExists(FriendshipError):
    """Заявка от me→other уже существует (pending)."""

    default_message = "Friend request already sent."
    default_code = "friendship_exists"
    status_code = 409


class AlreadyFriends(FriendshipError):
    default_message = "You are already friends."
    default_code = "already_friends"
    status_code = 409


class UserBlocked(FriendshipError):
    """Один из юзеров заблокировал другого."""

    default_message = "Cannot send friend request to this user."
    default_code = "user_blocked"
    status_code = 403


class FriendshipNotFound(FriendshipError):
    default_message = "Friend request not found."
    default_code = "friendship_not_found"
    status_code = 404


class NotRecipient(FriendshipError):
    """Попытка accept/decline не своей входящей заявки."""

    default_message = "You are not the recipient of this friend request."
    default_code = "not_recipient"
    status_code = 403


class TargetUserNotFound(FriendshipError):
    default_message = "Target user not found."
    default_code = "user_not_found"
    status_code = 404
