"""Cursor-пагинация для ленты постов и комментариев."""

from __future__ import annotations

from rest_framework.pagination import CursorPagination


class PostCursorPagination(CursorPagination):
    """
    Лента постов: новые сверху. Tiebreak по id обязателен — без него курсор
    может пропустить/повторить записи с одинаковым created_at.
    """

    page_size = 15
    max_page_size = 30
    ordering = ("-created_at", "-id")
    cursor_query_param = "cursor"


class PostCommentCursorPagination(CursorPagination):
    """
    Комментарии: старые сверху (created_at asc), клиент дописывает свежие вниз.
    """

    page_size = 50
    max_page_size = 100
    ordering = ("created_at", "id")
    cursor_query_param = "cursor"
