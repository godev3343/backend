"""
Image processing: decode → EXIF strip → resize → WebP encode.

Чистый модуль без R2 и Celery — функции работают с bytes и Pillow-объектами.
Это упрощает тестирование (нет I/O) и позволяет переиспользовать логику.

Решения:
- WebP для feed/thumb всегда (см. ТЗ 4.4). Оригинал — тоже WebP при resize,
  иначе остаётся в исходном формате если меньше 2048px (экономим CPU).
- LANCZOS-resampling — лучший downscale-фильтр в Pillow.
- ImageOps.exif_transpose — поворачивает по EXIF Orientation ДО strip'а,
  иначе iPhone-фото будут перевёрнуты.
- HEIC через pillow-heif.register_heif_opener() — Pillow видит .heic/.heif
  как нативный формат после этого.
- Качество WebP: 90 для original, 85 для feed, 80 для thumb.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Literal

import pillow_heif
from PIL import Image, ImageOps, UnidentifiedImageError

# Регистрируем HEIC-декодер один раз на импорт модуля.
pillow_heif.register_heif_opener()

logger = logging.getLogger(__name__)


# Размеры по длинной стороне.
ORIGINAL_MAX = 2048
FEED_MAX = 1080
THUMB_MAX = 320

# WebP качество для каждого варианта.
ORIGINAL_QUALITY = 90
FEED_QUALITY = 85
THUMB_QUALITY = 80

Variant = Literal["original", "feed", "thumb"]


class ImageProcessingError(Exception):
    """Ошибка при обработке картинки (битый файл, неподдерживаемый формат)."""


class ImageTooSmallError(ImageProcessingError):
    """Картинка меньше минимально допустимого размера."""


@dataclass(frozen=True)
class ProcessedVariant:
    """Один обработанный вариант — байты webp и его финальные размеры."""

    variant: Variant
    data: bytes
    width: int
    height: int


@dataclass(frozen=True)
class ProcessedImage:
    """Все три варианта + исходные размеры (после EXIF transpose)."""

    source_width: int
    source_height: int
    original: ProcessedVariant
    feed: ProcessedVariant
    thumb: ProcessedVariant


def _decode(data: bytes) -> Image.Image:
    """Открыть картинку из bytes. Бросает ImageProcessingError на битых файлах."""
    try:
        img = Image.open(io.BytesIO(data))
        # Pillow ленивый — заставляем декодировать сразу, чтобы поймать
        # ошибку здесь, а не где-то дальше при resize.
        img.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ImageProcessingError(f"Cannot decode image: {exc}") from exc
    return img


def _normalize(img: Image.Image) -> Image.Image:
    """
    Подготовить картинку к ресайзу:
    - повернуть по EXIF Orientation
    - сконвертировать в RGB (WebP не пишет RGBA при quality<100 нормально,
      и для аватаров/feed альфа не нужна; если будут стикеры — пересмотрим)
    """
    img = ImageOps.exif_transpose(img) or img

    if img.mode in ("RGBA", "LA", "P"):
        # P/LA конвертируем через RGBA чтобы не потерять прозрачность как чёрный
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        # Подкладываем белый фон под прозрачные пиксели — выглядит лучше
        # чем чёрный (дефолт WebP при alpha=0 в lossy mode)
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])  # alpha как маска
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    return img


def _resize_if_larger(img: Image.Image, target: int) -> Image.Image:
    """
    Уменьшить если длинная сторона > target. Иначе вернуть как есть.
    Никогда НЕ апскейлим — это размывает картинку без пользы.

    Image.thumbnail работает in-place и сохраняет aspect ratio.
    """
    if max(img.size) <= target:
        return img
    # Копию делаем чтобы оригинал не мутировать — нужен для других вариантов
    out = img.copy()
    out.thumbnail((target, target), Image.Resampling.LANCZOS)
    return out


def _encode_webp(img: Image.Image, quality: int) -> bytes:
    """Сохранить картинку в WebP-bytes. method=6 — лучшее сжатие за CPU."""
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=6)
    return buf.getvalue()


def process(data: bytes, *, min_short_side: int) -> ProcessedImage:
    """
    Полный пайплайн: bytes → 3 варианта.

    Args:
        data: bytes исходной картинки (любой поддерживаемый формат)
        min_short_side: минимальная короткая сторона в пикселях; меньше — фейл

    Raises:
        ImageProcessingError — нечитаемая картинка
        ImageTooSmallError — короткая сторона < min_short_side
    """
    src = _decode(data)
    src = _normalize(src)

    short_side = min(src.size)
    if short_side < min_short_side:
        raise ImageTooSmallError(
            f"Short side {short_side}px < min {min_short_side}px"
        )

    source_w, source_h = src.size

    # Обрабатываем по убыванию — thumbnail работает быстрее на уже
    # уменьшенной картинке. Но для качества лучше каждый раз от оригинала
    # (LANCZOS на src даёт лучше результат). CPU-разница незначима для
    # картинок до 20MB.
    orig_img = _resize_if_larger(src, ORIGINAL_MAX)
    feed_img = _resize_if_larger(src, FEED_MAX)
    thumb_img = _resize_if_larger(src, THUMB_MAX)

    return ProcessedImage(
        source_width=source_w,
        source_height=source_h,
        original=ProcessedVariant(
            variant="original",
            data=_encode_webp(orig_img, ORIGINAL_QUALITY),
            width=orig_img.size[0],
            height=orig_img.size[1],
        ),
        feed=ProcessedVariant(
            variant="feed",
            data=_encode_webp(feed_img, FEED_QUALITY),
            width=feed_img.size[0],
            height=feed_img.size[1],
        ),
        thumb=ProcessedVariant(
            variant="thumb",
            data=_encode_webp(thumb_img, THUMB_QUALITY),
            width=thumb_img.size[0],
            height=thumb_img.size[1],
        ),
    )