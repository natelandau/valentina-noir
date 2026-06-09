"""Tests for avatar image normalization."""

import io

import pytest
from PIL import Image

from vapi.lib.exceptions import ValidationError
from vapi.utils.images import AVATAR_SIZE, MAX_UPLOAD_BYTES, normalize_avatar


def _img_bytes(fmt: str, size: tuple[int, int] = (800, 600), mode: str = "RGB") -> bytes:
    """Build encoded image bytes of a given format/size for tests."""
    img = Image.new(mode, size, color=(120, 30, 30) if mode == "RGB" else (120, 30, 30, 255))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def test_normalize_avatar_returns_square_webp() -> None:
    """Verify a non-square PNG is normalized to a 512x512 WebP."""
    # Given a 800x600 PNG
    data = _img_bytes("PNG", size=(800, 600))

    # When normalizing
    result = normalize_avatar(data)

    # Then the result is a 512x512 WebP
    with Image.open(io.BytesIO(result)) as out:
        assert out.format == "WEBP"
        assert out.size == (AVATAR_SIZE, AVATAR_SIZE)


def test_normalize_avatar_accepts_jpeg() -> None:
    """Verify a JPEG is accepted and re-encoded to WebP."""
    # Given a JPEG
    data = _img_bytes("JPEG", size=(1000, 1000))

    # When normalizing
    result = normalize_avatar(data)

    # Then the result is WebP
    with Image.open(io.BytesIO(result)) as out:
        assert out.format == "WEBP"


def test_normalize_avatar_first_frame_of_gif() -> None:
    """Verify an animated GIF is flattened to a single-frame WebP."""
    # Given a 2-frame animated GIF
    frame_a = Image.new("P", (300, 300), color=1)
    frame_b = Image.new("P", (300, 300), color=2)
    buf = io.BytesIO()
    frame_a.save(buf, format="GIF", save_all=True, append_images=[frame_b], duration=100)
    data = buf.getvalue()

    # When normalizing
    result = normalize_avatar(data)

    # Then the result is a single 512x512 WebP (no animation)
    with Image.open(io.BytesIO(result)) as out:
        assert out.format == "WEBP"
        assert out.size == (AVATAR_SIZE, AVATAR_SIZE)
        assert getattr(out, "n_frames", 1) == 1


def test_normalize_avatar_rejects_non_image() -> None:
    """Verify non-image bytes raise ValidationError."""
    # Given bytes that are not an image
    data = b"this is not an image"

    # When/Then normalizing raises ValidationError
    with pytest.raises(ValidationError):
        normalize_avatar(data)


def test_normalize_avatar_rejects_disallowed_format() -> None:
    """Verify a disallowed image format (BMP) raises ValidationError."""
    # Given a BMP image (not in the allowlist)
    data = _img_bytes("BMP", size=(400, 400))

    # When/Then normalizing raises ValidationError
    with pytest.raises(ValidationError):
        normalize_avatar(data)


def test_normalize_avatar_rejects_oversized_upload() -> None:
    """Verify an upload larger than the cap raises ValidationError before decoding."""
    # Given a payload larger than MAX_UPLOAD_BYTES
    data = b"\x00" * (MAX_UPLOAD_BYTES + 1)

    # When/Then normalizing raises ValidationError
    with pytest.raises(ValidationError):
        normalize_avatar(data)
