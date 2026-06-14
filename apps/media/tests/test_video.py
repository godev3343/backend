"""Юнит-тесты извлечения постера видео (без реального ffmpeg)."""

from __future__ import annotations

import pytest

from apps.media.services.video import VideoProcessingError, extract_poster_frame


def test_missing_ffmpeg_binary_raises(settings) -> None:  # type: ignore[no-untyped-def]
    """Нет бинаря ffmpeg по пути → VideoProcessingError (а не голый OSError)."""
    settings.FFMPEG_BIN = "/nonexistent/path/ffmpeg-does-not-exist"
    with pytest.raises(VideoProcessingError):
        extract_poster_frame(b"not-a-real-video")
