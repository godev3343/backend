"""Cursor-пагинация для истории поинтов."""

from __future__ import annotations

from rest_framework.pagination import CursorPagination


class PointsHistoryCursorPagination(CursorPagination):
    """
    50 записей по умолчанию (по ТЗ декомпозиции 9.2: "последних 50 транзакций").
    Cursor по (-created_at, -id) — стабильный tiebreak при одинаковом timestamp
    (бывает в тестах и при batch-операциях).
    """

    page_size = 50
    max_page_size = 50
    ordering = ("-created_at", "-id")
    cursor_query_param = "cursor"
