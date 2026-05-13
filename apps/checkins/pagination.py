"""Cursor-пагинация для чек-инов и ленты."""

from __future__ import annotations

from rest_framework.pagination import CursorPagination


class CheckInCursorPagination(CursorPagination):
    """
    Cursor по (-created_at, -id). Tiebreak по id обязателен — без него
    курсор может пропустить/повторить записи с одинаковым timestamp
    (бывает в тестах и при batch-импорте).
    """

    page_size = 20
    max_page_size = 50
    ordering = ("-created_at", "-id")
    cursor_query_param = "cursor"
