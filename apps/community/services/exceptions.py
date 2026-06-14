"""
Доменные ошибки сообщества. Наследуются от DomainError → api_exception_handler
сам конвертирует их в {detail, code}.
"""

from __future__ import annotations

from rest_framework import status

from apps.core.exceptions import DomainError


class CommunityError(DomainError):
    """Базовая ошибка домена сообщества."""

    default_code = "community_error"
    default_message = "Community error."
    status_code = 400


class PostNotFound(CommunityError):
    default_code = "post_not_found"
    default_message = "Post not found."
    status_code = status.HTTP_404_NOT_FOUND


class CommentNotFound(CommunityError):
    default_code = "comment_not_found"
    default_message = "Comment not found."
    status_code = status.HTTP_404_NOT_FOUND


class PostMediaNotFound(CommunityError):
    default_code = "post_media_not_found"
    default_message = "Media not found, wrong type, or not owned by you."


class PostMediaNotReady(CommunityError):
    default_code = "post_media_not_ready"
    default_message = "Media is still being processed. Try again in a moment."
