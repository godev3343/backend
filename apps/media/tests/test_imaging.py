"""Тесты image processing — Pillow pipeline без R2."""
from __future__ import annotations

import io

import pytest
from PIL import Image

from apps.media.services import imaging


def _make_image(
    *,
    width: int = 1500,
    height: int = 1000,
    mode: str = "RGB",
    fmt: str = "JPEG",
) -> bytes:
    """Сгенерировать тестовую картинку нужного размера/формата."""
    img = Image.new(mode, (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


class TestProcess:
    def test_large_image_downscales_all(self) -> None:
        data = _make_image(width=4000, height=3000)
        result = imaging.process(data, min_short_side=400)

        assert result.source_width == 4000
        assert result.source_height == 3000

        assert max(result.original.width, result.original.height) == imaging.ORIGINAL_MAX
        assert max(result.feed.width, result.feed.height) == imaging.FEED_MAX
        assert max(result.thumb.width, result.thumb.height) == imaging.THUMB_MAX

        # aspect ratio сохранён (4:3)
        assert result.original.width / result.original.height == pytest.approx(4 / 3, rel=0.01)

    def test_medium_image_original_unchanged(self) -> None:
        data = _make_image(width=1500, height=1000)
        result = imaging.process(data, min_short_side=400)

        assert result.original.width == 1500
        assert result.original.height == 1000
        assert max(result.feed.width, result.feed.height) == imaging.FEED_MAX
        assert max(result.thumb.width, result.thumb.height) == imaging.THUMB_MAX

    def test_small_image_no_upscale(self) -> None:
        data = _make_image(width=600, height=500)
        result = imaging.process(data, min_short_side=400)

        assert result.original.width == 600
        assert result.original.height == 500
        assert result.feed.width == 600
        assert result.feed.height == 500
        assert max(result.thumb.width, result.thumb.height) == imaging.THUMB_MAX

    def test_tiny_image_all_unchanged(self) -> None:
        data = _make_image(width=410, height=410)
        result = imaging.process(data, min_short_side=400)

        assert result.original.width == 410
        assert result.feed.width == 410
        assert max(result.thumb.width, result.thumb.height) == imaging.THUMB_MAX

    def test_too_small_rejected(self) -> None:
        data = _make_image(width=200, height=200)
        with pytest.raises(imaging.ImageTooSmallError):
            imaging.process(data, min_short_side=400)

    def test_short_side_landscape(self) -> None:
        data = _make_image(width=1000, height=300)
        with pytest.raises(imaging.ImageTooSmallError):
            imaging.process(data, min_short_side=400)

    def test_invalid_format(self) -> None:
        with pytest.raises(imaging.ImageProcessingError):
            imaging.process(b"not an image at all", min_short_side=10)

    def test_truncated_jpeg(self) -> None:
        data = _make_image()
        with pytest.raises(imaging.ImageProcessingError):
            imaging.process(data[:50], min_short_side=10)

    def test_png_with_alpha_converted(self) -> None:
        data = _make_image(width=800, height=600, mode="RGBA", fmt="PNG")
        result = imaging.process(data, min_short_side=400)
        out_img = Image.open(io.BytesIO(result.feed.data))
        assert out_img.format == "WEBP"
        assert out_img.size == (800, 600)

    def test_output_is_webp(self) -> None:
        data = _make_image()
        result = imaging.process(data, min_short_side=400)

        for variant in (result.original, result.feed, result.thumb):
            img = Image.open(io.BytesIO(variant.data))
            assert img.format == "WEBP"


class TestNormalize:
    def test_no_exif_no_crash(self) -> None:
        data = _make_image(width=800, height=600)
        result = imaging.process(data, min_short_side=400)
        assert result.source_width == 800
        assert result.source_height == 600