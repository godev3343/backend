"""
Cursor-pagination для лент чек-инов.

Выбор cursor вместо offset:
- На ленте друзей offset → DoS-вектор (большие OFFSET сканируют лишнее).
- Cursor стабильно работает при вставке новых чек-инов в начало.

Сортировка по (-created_at, -id) — second key обязателен, иначе при
одинаковом timestamp курсор может либо повторить чек-ины, либо пропустить.
"""
from __future__ import annotations

from rest_framework.pagination import CursorPagination


class CheckInCursorPagination(CursorPagination):
    """Cursor pagination на (-created_at, -id). Page size 20, max 50."""

    page_size = 20
    page_size_query_param = "limit"
    max_page_size = 50
    ordering = ("-created_at", "-id")
    cursor_query_param = "cursor"