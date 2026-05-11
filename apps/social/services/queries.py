"""
Аннотация friendship_status на User-queryset.

Используется в /api/users/{id}, /api/users/search, чтобы фронт мог
показывать корректную кнопку (Add / Accept / Cancel / Friends) без
N+1 запросов.

Возможные значения friendship_status:
- "none"               — отношений нет
- "pending_outgoing"   — я отправил заявку, ответа нет
- "pending_incoming"   — мне отправили заявку, я не ответил
- "friends"            — мы друзья (accepted с любой стороны)
- "blocked"            — кто-то кого-то заблокировал
- "self"               — это я сам

Реализация — четыре EXISTS-subquery, проверяющих наличие записей в
Friendship для каждого из статусов. Дешевле, чем выгребать Friendship и
матчить в Python.
"""
from __future__ import annotations

from django.db.models import (
    BooleanField,
    Case,
    Exists,
    OuterRef,
    Q,
    QuerySet,
    Value,
    When,
)

from apps.social.models import Friendship, FriendshipStatus


def annotate_friendship_status(
    qs: QuerySet, *, viewer_id: int | None
) -> QuerySet:
    """
    Аннотирует каждого User в qs полем `friendship_status` относительно
    viewer (request.user).

    Если viewer не аутентифицирован (viewer_id=None) — все юзеры получают
    статус "none".
    """
    if viewer_id is None:
        # Анонимам всё равно нужно поле — пусть будет "none", чтобы
        # сериализатор не падал.
        return qs.annotate(
            friendship_status=Value("none", output_field=_str_field())
        )

    # Self — отдельная аннотация
    is_self = Case(
        When(pk=viewer_id, then=Value(True)),
        default=Value(False),
        output_field=BooleanField(),
    )

    # accepted в обе стороны: viewer → other OR other → viewer
    accepted_subq = Friendship.objects.filter(
        Q(from_user_id=viewer_id, to_user_id=OuterRef("pk"))
        | Q(from_user_id=OuterRef("pk"), to_user_id=viewer_id),
        status=FriendshipStatus.ACCEPTED,
    )

    # blocked — также в обе стороны
    blocked_subq = Friendship.objects.filter(
        Q(from_user_id=viewer_id, to_user_id=OuterRef("pk"))
        | Q(from_user_id=OuterRef("pk"), to_user_id=viewer_id),
        status=FriendshipStatus.BLOCKED,
    )

    # pending outgoing: viewer → other, pending
    pending_out_subq = Friendship.objects.filter(
        from_user_id=viewer_id,
        to_user_id=OuterRef("pk"),
        status=FriendshipStatus.PENDING,
    )

    # pending incoming: other → viewer, pending
    pending_in_subq = Friendship.objects.filter(
        from_user_id=OuterRef("pk"),
        to_user_id=viewer_id,
        status=FriendshipStatus.PENDING,
    )

    return qs.annotate(
        _is_self=is_self,
        _is_friends=Exists(accepted_subq),
        _is_blocked=Exists(blocked_subq),
        _is_pending_out=Exists(pending_out_subq),
        _is_pending_in=Exists(pending_in_subq),
        friendship_status=Case(
            When(_is_self=True, then=Value("self")),
            When(_is_friends=True, then=Value("friends")),
            When(_is_blocked=True, then=Value("blocked")),
            When(_is_pending_out=True, then=Value("pending_outgoing")),
            When(_is_pending_in=True, then=Value("pending_incoming")),
            default=Value("none"),
            output_field=_str_field(),
        ),
    )


def _str_field():  # type: ignore[no-untyped-def]
    """CharField для output_field в Value/Case."""
    from django.db.models import CharField

    return CharField(max_length=32)