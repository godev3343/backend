"""
Извлечение постера (первого кадра) из видео через ffmpeg.

Чистый модуль: на вход bytes видео, на выход bytes кадра (PNG). R2/Celery —
снаружи (в tasks.process_video). Кадр дальше прогоняется тем же Pillow-
пайплайном (imaging.process), что и фото — DRY.

ffmpeg — системный бинарь (ставится в deploy/Dockerfile). Путь настраивается
через settings.FFMPEG_BIN.
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

# Секунда, с которой берём кадр. Первый кадр (0s) часто чёрный/заставка —
# секунда даёт более репрезентативный постер. Если видео короче — фолбэк на 0.
POSTER_AT_SECOND = 1.0

# Жёсткий таймаут на вызов ffmpeg, чтобы битый файл не повесил воркер.
_FFMPEG_TIMEOUT_S = 60


class VideoProcessingError(Exception):
    """ffmpeg не смог извлечь кадр (битый файл, не видео, нет бинаря)."""


def extract_poster_frame(data: bytes, *, at_second: float = POSTER_AT_SECOND) -> bytes:
    """
    Достать один кадр из видео как PNG-bytes.

    mp4 требует seekable-вход (moov-atom), поэтому пишем во временный файл,
    а не в stdin. Если кадр на at_second пуст (видео короче) — фолбэк на 0s.

    Raises:
        VideoProcessingError — ffmpeg не найден / упал / не отдал кадр.
    """
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        frame = _run_ffmpeg_frame(tmp_path, at_second)
        if not frame:
            # at_second мог оказаться за пределами длительности — берём первый кадр.
            frame = _run_ffmpeg_frame(tmp_path, 0.0)
        if not frame:
            raise VideoProcessingError("ffmpeg produced no frame")
        return frame
    finally:
        try:
            Path(tmp_path).unlink()
        except OSError:
            logger.warning("failed to remove temp video file %s", tmp_path)


def _run_ffmpeg_frame(path: str, at_second: float) -> bytes:
    """Один вызов ffmpeg: PNG-кадр в stdout. Пустой stdout — не ошибка (фолбэк)."""
    cmd = [
        settings.FFMPEG_BIN,
        "-nostdin",
        "-loglevel",
        "error",
        "-ss",
        str(at_second),
        "-i",
        path,
        "-frames:v",
        "1",
        "-an",
        "-f",
        "image2pipe",
        "-vcodec",
        "png",
        "-",
    ]
    # cmd фиксированный, path из tempfile (не пользовательский ввод).
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=_FFMPEG_TIMEOUT_S,
            check=False,
        )
    except FileNotFoundError as exc:
        raise VideoProcessingError(f"ffmpeg binary not found: {settings.FFMPEG_BIN}") from exc
    except subprocess.TimeoutExpired as exc:
        raise VideoProcessingError("ffmpeg timed out") from exc

    if proc.returncode != 0:
        stderr = proc.stderr.decode("utf-8", errors="replace")[:500]
        raise VideoProcessingError(f"ffmpeg failed (rc={proc.returncode}): {stderr}")

    return proc.stdout
