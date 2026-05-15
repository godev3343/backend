"""
Endpoints загрузки медиа.

POST /api/upload/presign  — получить presigned PUT URL
POST /api/upload/confirm  — подтвердить загрузку, поставить процессинг

GET /api/media/{id}       — статус asset'а (опционально, для polling-а
                            процессинга на фронте)
"""

from __future__ import annotations

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.media.models import MediaAsset
from apps.media.serializers import (
    ConfirmRequestSerializer,
    MediaAssetSerializer,
    PresignRequestSerializer,
)
from apps.media.services.exceptions import MediaAssetNotFound
from apps.media.services.upload import UploadService
from apps.users.permissions import IsEmailVerified

from drf_spectacular.utils import extend_schema

from apps.core.serializers import DetailSerializer, EmptySerializer


@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
class PresignView(APIView):
    """
    POST /api/upload/presign

    Body:
        {
            "purpose": "avatar" | "checkin" | "place",
            "content_type": "image/jpeg",
            "content_length": 1234567
        }

    Response 201:
        {
            "asset_id": 42,
            "upload_url": "https://...r2...?X-Amz-Signature=...",
            "key": "avatars/42/9c1.../original.jpg",
            "expires_in": 300
        }
    """

    permission_classes = [IsAuthenticated, IsEmailVerified]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "upload_presign"

    def post(self, request: Request) -> Response:
        ser = PresignRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        result = UploadService.presign(
            user=request.user,
            purpose=ser.validated_data["purpose"],
            content_type=ser.validated_data["content_type"],
            content_length=ser.validated_data["content_length"],
        )

        return Response(
            {
                "asset_id": result.asset_id,
                "upload_url": result.upload_url,
                "key": result.key,
                "expires_in": result.expires_in,
            },
            status=status.HTTP_201_CREATED,
        )


@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
class ConfirmView(APIView):
    """
    POST /api/upload/confirm

    Body:
        {"asset_id": 42}

    Response 200:
        MediaAsset (status=pending; status станет processed после Celery-таски)
    """

    permission_classes = [IsAuthenticated, IsEmailVerified]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "upload_confirm"

    def post(self, request: Request) -> Response:
        ser = ConfirmRequestSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        asset = UploadService.confirm(
            user=request.user,
            asset_id=ser.validated_data["asset_id"],
        )

        return Response(MediaAssetSerializer(asset).data, status=status.HTTP_200_OK)


@extend_schema(request=EmptySerializer, responses=DetailSerializer, tags=["auth"])
class MediaAssetDetailView(APIView):
    """
    GET /api/media/{asset_id}

    Возвращает текущее состояние asset'а. Фронт может polling-ом ждать
    PROCESSED после confirm — в EPIC 0 у нас polling-стратегия для realtime.

    Видеть свой asset разрешено в любом статусе. Чужие — 404 (не 403, чтобы
    не подтверждать факт существования id чужого юзера).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, asset_id: int) -> Response:
        try:
            asset = MediaAsset.objects.get(pk=asset_id, owner=request.user)
        except MediaAsset.DoesNotExist as exc:
            raise MediaAssetNotFound() from exc

        return Response(MediaAssetSerializer(asset).data)
