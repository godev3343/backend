"""
REST-эндпоинты чата (CHAT_BACKEND_SPEC §2):
- GET  /api/chats                          — список переписок (sort updated_at desc)
- POST /api/chats                          — создать/получить переписку с другом
- GET  /api/chats/{id}/messages            — история сообщений (пагинация)

View тонкий: валидация → ChatService → сериализация. Доступ — только
друзьям-участникам (IsEmailVerified + IsOnboarded, как у friends-эндпоинтов).
Пути без trailing slash (контракт клиента). Пагинация — LimitOffsetPagination.
"""

from __future__ import annotations

from uuid import UUID

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.chat.models import Conversation, Message
from apps.chat.serializers import (
    ChatMessageSerializer,
    ConversationSerializer,
    CreateConversationSerializer,
)
from apps.chat.services import ChatService, PresenceService
from apps.core.serializers import DetailSerializer
from apps.users.permissions import IsEmailVerified, IsOnboarded

_PROTECTED = [IsAuthenticated, IsEmailVerified, IsOnboarded]


def _serialize_conversation(conversation: Conversation, *, viewer_id: int) -> dict:
    """Сериализовать одну переписку с presence-снапшотом собеседника."""
    peer_id = ChatService.peer_id(conversation, viewer_id)
    online_map = PresenceService.online_map([peer_id])
    return ConversationSerializer(
        conversation, context={"viewer_id": viewer_id, "online_map": online_map}
    ).data


@extend_schema(tags=["chat"])
class ConversationListCreateView(GenericAPIView):
    """GET — список переписок; POST — создать/получить переписку с другом."""

    permission_classes = _PROTECTED
    pagination_class = LimitOffsetPagination
    serializer_class = ConversationSerializer
    queryset = Conversation.objects.none()  # для генерации схемы drf-spectacular

    @extend_schema(
        summary="Список переписок",
        description=(
            "Переписки текущего пользователя, отсортированные по времени "
            "последней активности (`updated_at` desc). Пагинация limit/offset."
        ),
        responses={200: ConversationSerializer(many=True), 401: DetailSerializer},
    )
    def get(self, request: Request) -> Response:
        qs = ChatService.list_conversations(user=request.user)
        paginator = self.pagination_class()
        page = list(paginator.paginate_queryset(qs, request, view=self))

        # Батч presence для всех собеседников страницы — один pipeline.
        peer_ids = [ChatService.peer_id(c, request.user.pk) for c in page]
        online_map = PresenceService.online_map(peer_ids)

        data = ConversationSerializer(
            page,
            many=True,
            context={"viewer_id": request.user.pk, "online_map": online_map},
        ).data
        return paginator.get_paginated_response(data)

    @extend_schema(
        summary="Создать/получить переписку с другом",
        description=(
            "Идемпотентно: если переписка с `user_id` уже есть — возвращает её "
            "(200), иначе создаёт (201). `user_id` должен быть другом текущего "
            "пользователя, иначе 403."
        ),
        request=CreateConversationSerializer,
        responses={
            200: ConversationSerializer,
            201: ConversationSerializer,
            400: DetailSerializer,
            401: DetailSerializer,
            403: DetailSerializer,
            404: DetailSerializer,
        },
    )
    def post(self, request: Request) -> Response:
        serializer = CreateConversationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        conversation, created = ChatService.get_or_create_conversation(
            user=request.user, peer_id=serializer.validated_data["user_id"]
        )
        # Перечитываем через list_conversations — чтобы отдать ту же форму
        # (аннотация unread + префетч participants/last_message), что и в GET.
        conversation = ChatService.list_conversations(user=request.user).get(pk=conversation.pk)
        data = _serialize_conversation(conversation, viewer_id=request.user.pk)
        return Response(
            data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


@extend_schema(
    tags=["chat"],
    summary="История сообщений переписки",
    description=(
        "Сообщения одной переписки, новые первыми (`created_at` desc). Доступ "
        "только участнику переписки. Пагинация limit/offset."
    ),
    parameters=[
        OpenApiParameter(
            name="conversation_id",
            type=str,
            location=OpenApiParameter.PATH,
            description="UUID переписки",
        )
    ],
    responses={
        200: ChatMessageSerializer(many=True),
        401: DetailSerializer,
        404: DetailSerializer,
    },
)
class MessageListView(GenericAPIView):
    """GET /api/chats/{id}/messages — история сообщений."""

    permission_classes = _PROTECTED
    pagination_class = LimitOffsetPagination
    serializer_class = ChatMessageSerializer
    queryset = Message.objects.none()  # для генерации схемы drf-spectacular

    def get(self, request: Request, conversation_id: UUID) -> Response:
        qs = ChatService.get_messages(user=request.user, conversation_id=conversation_id)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request, view=self)
        serializer = self.get_serializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
