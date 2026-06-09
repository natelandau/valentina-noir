"""Tests for avatar image normalization."""

import io

import pytest
from PIL import Image

from vapi.lib.exceptions import ValidationError
from vapi.utils.images import (
    AVATAR_SIZE,
    MAX_UPLOAD_BYTES,
    normalize_avatar,
    validate_image_upload,
)


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


def test_normalize_avatar_rejects_decompression_bomb() -> None:
    """Verify an image exceeding the pixel-count guard raises ValidationError."""
    # Given an image whose pixel count exceeds Pillow's decompression-bomb threshold
    import PIL.Image

    bomb_pixels = PIL.Image.MAX_IMAGE_PIXELS * 2 + 1
    side = int(bomb_pixels**0.5) + 1
    buf = io.BytesIO()
    PIL.Image.new("RGB", (side, side)).save(buf, format="PNG")
    data = buf.getvalue()

    # The solid-color PNG compresses tiny, so the bomb branch (not the size cap) is exercised
    assert len(data) < MAX_UPLOAD_BYTES

    # When/Then normalizing raises ValidationError (not an uncaught DecompressionBombError)
    with pytest.raises(ValidationError):
        normalize_avatar(data)


@pytest.mark.parametrize(
    ("fmt", "expected_mime"),
    [
        ("PNG", "image/png"),
        ("JPEG", "image/jpeg"),
        ("GIF", "image/gif"),
        ("WEBP", "image/webp"),
    ],
)
def test_validate_image_upload_returns_detected_mime(fmt: str, expected_mime: str) -> None:
    """Verify each allowed format returns its canonical MIME type detected from the bytes."""
    # Given a real image of an allowed format
    data = _img_bytes(fmt, size=(400, 400))

    # When validating the upload
    result = validate_image_upload(data=data)

    # Then the canonical MIME type for the detected format is returned
    assert result == expected_mime


def test_validate_image_upload_rejects_spoofed_content_type() -> None:
    """Verify bytes that are not a decodable image raise ValidationError."""
    # Given HTML bytes masquerading as a PNG
    data = b"<html><script>alert(1)</script></html>"

    # When/Then validation rejects the spoofed upload
    with pytest.raises(ValidationError):
        validate_image_upload(data=data)


def test_validate_image_upload_rejects_disallowed_format() -> None:
    """Verify a decodable image in a disallowed format (BMP) is rejected."""
    # Given a valid BMP image, which is not in the allowed format set
    data = _img_bytes("BMP", size=(400, 400))

    # When/Then validation rejects the disallowed format
    with pytest.raises(ValidationError):
        validate_image_upload(data=data)


def test_validate_image_upload_rejects_svg() -> None:
    """Verify an SVG (XML, not a raster image) is rejected."""
    # Given SVG markup
    data = b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'

    # When/Then validation rejects the SVG (it does not decode as a raster image)
    with pytest.raises(ValidationError):
        validate_image_upload(data=data)


def test_validate_image_upload_rejects_decompression_bomb() -> None:
    """Verify an image exceeding the pixel-count guard is rejected."""
    # Given a PNG whose pixel count exceeds Pillow's decompression-bomb threshold
    import PIL.Image

    bomb_pixels = PIL.Image.MAX_IMAGE_PIXELS * 2 + 1
    side = int(bomb_pixels**0.5) + 1
    buf = io.BytesIO()
    PIL.Image.new("RGB", (side, side)).save(buf, format="PNG")
    data = buf.getvalue()

    # When/Then validation rejects the bomb rather than raising DecompressionBombError
    with pytest.raises(ValidationError):
        validate_image_upload(data=data)


def test_validate_image_upload_rejects_corrupt_image_without_crashing() -> None:
    """Verify a structurally-broken image raises ValidationError, not a raw decoder error."""
    # Given a PNG that opens but has a corrupted IDAT chunk (verify() raises SyntaxError)
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, format="PNG")
    raw = bytearray(buf.getvalue())
    raw[raw.find(b"IDAT") + 8] ^= 0xFF  # Flip a data byte so the chunk CRC no longer matches.
    data = bytes(raw)

    # When/Then validation surfaces a clean ValidationError instead of leaking SyntaxError
    with pytest.raises(ValidationError):
        validate_image_upload(data=data)
