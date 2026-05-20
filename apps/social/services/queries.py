# apps/social/services/queries.py
"""
Аннотация friendship_status + friendship_id на User-queryset.

Используется в /api/users/{id}, /api/users/search, чтобы фронт мог
показывать корректную кнопку (Add / Accept / Cancel / Friends) без
N+1 запросов и без дополнительного fetch'а кеша заявок.

Возможные значения friendship_status:
- "none"               — отношений нет
- "pending_outgoing"   — я отправил заявку, ответа нет
- "pending_incoming"   — мне отправили заявку, я не ответил
- "friends"            — мы друзья (accepted с любой стороны)
- "blocked"            — кто-то кого-то заблокировал
- "self"               — это я сам

friendship_id:
- Не null только для pending_outgoing / pending_incoming.
- Нужен фронту для cancel/accept/decline-эндпоинтов, которые принимают
  именно Friendship.pk, а не user_id.
- Для friends/blocked/none/self — null (фронту не нужен).

Реализация — пять Subquery: четыре EXISTS для статуса + одна Subquery с
Friendship.pk для pending. Дешевле, чем выгребать Friendship и матчить
в Python; OuterRef разруливает корреляцию.
"""

from __future__ import annotations

from django.db.models import (
    BooleanField,
    Case,
    CharField,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)

from apps.social.models import Friendship, FriendshipStatus


def annotate_friendship_status(qs: QuerySet, *, viewer_id: int | None) -> QuerySet:
    """
    Аннотирует каждого User в qs полями `friendship_status` и `friendship_id`
    относительно viewer (request.user).

    Если viewer не аутентифицирован (viewer_id=None) — все юзеры получают
    статус "none" и friendship_id=null.
    """
    if viewer_id is None:
        return qs.annotate(
            friendship_status=Value("none", output_field=_str_field()),
            friendship_id=Value(None, output_field=IntegerField(null=True)),
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

    # friendship_id для pending — берём ровно одну запись через Subquery.
    # UniqueConstraint(from_user, to_user) гарантирует, что таких записей
    # в одну сторону не больше одной, поэтому [:1] безопасен.
    pending_out_id_subq = pending_out_subq.values("pk")[:1]
    pending_in_id_subq = pending_in_subq.values("pk")[:1]

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
        # null для friends/blocked/none/self; pk Friendship для pending
        friendship_id=Case(
            When(_is_pending_out=True, then=Subquery(pending_out_id_subq)),
            When(_is_pending_in=True, then=Subquery(pending_in_id_subq)),
            default=Value(None),
            output_field=IntegerField(null=True),
        ),
    )


def _str_field() -> CharField:
    """CharField для output_field в Value/Case."""
    return CharField(max_length=32)