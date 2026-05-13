"""
Cloudflare R2 client.

R2 — S3-совместимый object storage. Используем boto3 с кастомным endpoint.

Особенности R2 vs AWS S3:
- Регион всегда 'auto'.
- Нет server-side encryption-параметров.
- Public URL отдаётся через r2.dev поддомен или custom domain — оба
  настраиваются в Cloudflare dashboard и приходят к нам в R2_PUBLIC_URL.
- Bucket creation через консоль, не через API (можно через API, но смысла нет).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Literal

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


# Сигнатура SigV4. R2 требует именно её, иначе presigned URL не работает.
_SIGNATURE_VERSION = "s3v4"
# Регион для R2 всегда 'auto', иначе SDK генерирует невалидный signing key.
_REGION = "auto"


class R2Error(Exception):
    """Базовая ошибка работы с R2. Оборачиваем boto3-исключения."""


class R2ObjectNotFound(R2Error):
    """Объект по ключу не найден."""


@lru_cache(maxsize=1)
def _get_client():  # type: ignore[no-untyped-def]
    """
    Lazy singleton boto3 S3-клиента.

    lru_cache — потокобезопасный (modulo GIL) кэш. Boto3 client сам по себе
    потокобезопасен для большинства операций, поэтому один экземпляр на
    процесс — норма.
    """
    if not settings.R2_ENDPOINT_URL:
        raise R2Error("R2_ENDPOINT_URL is not configured")
    if not settings.R2_ACCESS_KEY or not settings.R2_SECRET_KEY:
        raise R2Error("R2 credentials are not configured")

    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY,
        aws_secret_access_key=settings.R2_SECRET_KEY,
        region_name=_REGION,
        config=Config(
            signature_version=_SIGNATURE_VERSION,
            retries={"max_attempts": 3, "mode": "standard"},
            # connect_timeout на presign-операциях бессмыслен (только подпись),
            # но read_timeout важен для head_object / delete_object.
            connect_timeout=5,
            read_timeout=10,
        ),
    )


# ----------------------------------------------------------------------------
# Presigned URLs
# ----------------------------------------------------------------------------


def generate_presigned_put(
    *,
    key: str,
    content_type: str,
    content_length: int,
    ttl_seconds: int | None = None,
) -> str:
    """
    Сгенерировать presigned PUT URL для прямой загрузки клиентом.

    Клиент должен использовать ТЕ ЖЕ значения Content-Type и Content-Length
    в заголовках при PUT, иначе R2 вернёт 403 SignatureDoesNotMatch.

    Args:
        key: ключ объекта в bucket (без bucket name)
        content_type: MIME-тип файла, например "image/jpeg"
        content_length: точный размер файла в байтах
        ttl_seconds: время жизни URL; None = settings.UPLOAD_PRESIGN_TTL
    """
    client = _get_client()
    expires = ttl_seconds if ttl_seconds is not None else settings.UPLOAD_PRESIGN_TTL

    try:
        return client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.R2_BUCKET,
                "Key": key,
                "ContentType": content_type,
                "ContentLength": content_length,
            },
            ExpiresIn=expires,
            HttpMethod="PUT",
        )
    except ClientError as exc:
        logger.exception("R2 presign failed: key=%s", key)
        raise R2Error(f"presign failed: {exc}") from exc


# ----------------------------------------------------------------------------
# Object operations
# ----------------------------------------------------------------------------


def head_object(key: str) -> dict[str, str | int]:
    """
    Получить метаданные объекта без скачивания тела.

    Returns:
        {"content_length": int, "content_type": str, "etag": str}

    Raises:
        R2ObjectNotFound — если объекта нет
        R2Error — любая другая ошибка
    """
    client = _get_client()
    try:
        response = client.head_object(Bucket=settings.R2_BUCKET, Key=key)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        # R2 возвращает '404' для отсутствующих объектов
        if code in ("404", "NoSuchKey", "NotFound"):
            raise R2ObjectNotFound(f"object not found: {key}") from exc
        logger.exception("R2 head failed: key=%s", key)
        raise R2Error(f"head failed: {exc}") from exc

    return {
        "content_length": int(response["ContentLength"]),
        "content_type": response.get("ContentType", "application/octet-stream"),
        "etag": response.get("ETag", "").strip('"'),
    }


def download_to_bytes(key: str) -> bytes:
    """
    Скачать объект целиком в память.

    Используем в process_image — картинки до 20 MB безопасно держать в RAM
    воркера (с учётом resize-буферов нужно ~3-4x от размера, для 20 MB это
    ~80 MB пиковой памяти на таску). При росте лимита заменим на streaming
    через temp-файл.

    Raises:
        R2ObjectNotFound — если объекта нет
        R2Error — любая другая ошибка
    """
    client = _get_client()
    try:
        response = client.get_object(Bucket=settings.R2_BUCKET, Key=key)
        return response["Body"].read()
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in ("NoSuchKey", "404", "NotFound"):
            raise R2ObjectNotFound(f"object not found: {key}") from exc
        logger.exception("R2 download failed: key=%s", key)
        raise R2Error(f"download failed: {exc}") from exc


def upload_bytes(
    *,
    key: str,
    data: bytes,
    content_type: str,
    cache_control: str = "public, max-age=31536000, immutable",
) -> None:
    """
    Загрузить bytes в R2.

    cache_control по умолчанию — immutable на год, потому что ключи у нас
    UUID-based (никогда не перезаписываются). Это даёт максимальный CDN-кэш.
    """
    client = _get_client()
    try:
        client.put_object(
            Bucket=settings.R2_BUCKET,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl=cache_control,
        )
    except ClientError as exc:
        logger.exception("R2 upload failed: key=%s", key)
        raise R2Error(f"upload failed: {exc}") from exc


def delete_object(key: str) -> None:
    """
    Удалить объект. Идемпотентно: на отсутствующий ключ не падает.

    R2 (как S3) на DELETE несуществующего объекта возвращает 204.
    """
    client = _get_client()
    try:
        client.delete_object(Bucket=settings.R2_BUCKET, Key=key)
    except ClientError as exc:
        logger.exception("R2 delete failed: key=%s", key)
        raise R2Error(f"delete failed: {exc}") from exc


def delete_objects(keys: list[str]) -> None:
    """
    Bulk-delete до 1000 ключей за один запрос.

    Используется когда удаляем MediaAsset с несколькими вариантами (orig +
    feed + thumb). Один запрос вместо трёх экономит Class A операцию.
    """
    if not keys:
        return
    if len(keys) > 1000:
        raise R2Error("delete_objects: max 1000 keys per request")

    client = _get_client()
    try:
        client.delete_objects(
            Bucket=settings.R2_BUCKET,
            Delete={"Objects": [{"Key": k} for k in keys], "Quiet": True},
        )
    except ClientError as exc:
        logger.exception("R2 bulk delete failed: keys=%d", len(keys))
        raise R2Error(f"bulk delete failed: {exc}") from exc


# ----------------------------------------------------------------------------
# URL helpers
# ----------------------------------------------------------------------------


Variant = Literal["original", "feed", "thumb"]


def build_public_url(key: str) -> str:
    """
    Превратить ключ объекта в публичный URL для отдачи фронту.

    R2_PUBLIC_URL — либо r2.dev поддомен (dev), либо custom domain (prod).
    Уже без trailing slash (стрипали в settings.py).
    """
    if not settings.R2_PUBLIC_URL:
        raise R2Error("R2_PUBLIC_URL is not configured")
    return f"{settings.R2_PUBLIC_URL}/{key}"
