"""Tests for avatar image normalization."""

import asyncio
import io
import json
import subprocess
import sys
import threading
import time
import warnings

import pytest
from PIL import ExifTags, Image, ImageDraw

from vapi.lib.exceptions import ValidationError
from vapi.utils.images import (
    AVATAR_SIZE,
    MAX_CONCURRENT_IMAGE_DECODES,
    MAX_IMAGE_PIXELS,
    MAX_UPLOAD_BYTES,
    normalize_avatar,
    run_image_decode,
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


def _over_budget_png() -> bytes:
    """Build a small PNG just over the pixel budget, below Pillow's 2x hard error."""
    buf = io.BytesIO()
    Image.new("L", (5000, MAX_IMAGE_PIXELS // 5000 + 1)).save(buf, format="PNG")
    return buf.getvalue()


def test_normalize_avatar_rejects_image_over_pixel_budget() -> None:
    """Verify an image over the pixel budget is rejected even when Pillow only warns."""
    # Given a PNG over the budget, with the bomb warning not escalated, as in production
    data = _over_budget_png()

    # When/Then normalizing raises ValidationError
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        with pytest.raises(ValidationError):
            normalize_avatar(data)


def test_validate_image_upload_rejects_image_over_pixel_budget() -> None:
    """Verify an asset upload over the pixel budget is rejected even when Pillow only warns."""
    # Given a PNG over the budget, with the bomb warning not escalated, as in production
    data = _over_budget_png()

    # When/Then validation raises ValidationError
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        with pytest.raises(ValidationError):
            validate_image_upload(data=data)


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


def test_normalize_avatar_scales_down_large_jpeg() -> None:
    """Verify a large JPEG avatar still normalizes to a 512x512 WebP after draft decoding."""
    # Given a 4000x3000 JPEG photo
    data = _img_bytes("JPEG", size=(4000, 3000))

    # When normalizing
    result = normalize_avatar(data)

    # Then the result is a 512x512 WebP
    with Image.open(io.BytesIO(result)) as out:
        assert out.format == "WEBP"
        assert out.size == (AVATAR_SIZE, AVATAR_SIZE)


@pytest.mark.anyio
async def test_run_image_decode_bounds_concurrency() -> None:
    """Verify image decodes never run more than the configured number at once."""
    # Given a decode stand-in that records how many copies run at the same time
    lock = threading.Lock()
    active = 0
    peak = 0

    def _decode(value: int) -> int:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return value

    # When many decodes are started together
    results = await asyncio.gather(*(run_image_decode(_decode, i) for i in range(8)))

    # Then every result comes back and concurrency stays within the bound
    assert results == list(range(8))
    assert peak <= MAX_CONCURRENT_IMAGE_DECODES


def test_normalize_avatar_honors_exif_orientation() -> None:
    """Verify the EXIF orientation is applied before the avatar is cropped and resized."""
    # Given a PNG with a red top half and blue bottom half, tagged "rotate 90 degrees clockwise"
    img = Image.new("RGB", (400, 400), (255, 0, 0))
    ImageDraw.Draw(img).rectangle((0, 200, 399, 399), fill=(0, 0, 255))
    exif = img.getexif()
    exif[ExifTags.Base.Orientation] = 6
    buf = io.BytesIO()
    img.save(buf, format="PNG", exif=exif)

    # When normalizing
    result = normalize_avatar(buf.getvalue())

    # Then the rotated image has blue on the left and red on the right
    with Image.open(io.BytesIO(result)) as out:
        rgb = out.convert("RGB")
        left = rgb.getpixel((100, 256))
        right = rgb.getpixel((400, 256))
    assert left[2] > 200 > left[0]
    assert right[0] > 200 > right[2]


def test_normalize_avatar_keeps_palette_transparency() -> None:
    """Verify a transparent palette pixel stays transparent in the normalized avatar."""
    # Given a palette GIF whose whole frame uses the transparent index
    img = Image.new("P", (300, 300), color=0)
    buf = io.BytesIO()
    img.save(buf, format="GIF", transparency=0)

    # When normalizing
    result = normalize_avatar(buf.getvalue())

    # Then the output pixels are fully transparent
    with Image.open(io.BytesIO(result)) as out:
        assert out.convert("RGBA").getpixel((256, 256))[3] == 0


def test_normalize_avatar_center_crops_large_wide_png() -> None:
    """Verify a large, wide PNG is center-cropped to the middle square and resized to 512x512."""
    # Given a 6000x2000 PNG that is green in its middle third and red outside it
    img = Image.new("RGB", (6000, 2000), (255, 0, 0))
    ImageDraw.Draw(img).rectangle((2000, 0, 3999, 1999), fill=(0, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    # When normalizing
    result = normalize_avatar(buf.getvalue())

    # Then the avatar is the green middle square, edge to edge
    with Image.open(io.BytesIO(result)) as out:
        assert out.size == (AVATAR_SIZE, AVATAR_SIZE)
        rgb = out.convert("RGB")
        for x in (2, 256, 509):
            pixel = rgb.getpixel((x, 256))
            assert pixel[1] > 200 > pixel[0]


@pytest.mark.parametrize(
    ("fmt", "save_kwargs"),
    [("PNG", {}), ("JPEG", {}), ("GIF", {}), ("WEBP", {}), ("WEBP", {"lossless": True})],
)
def test_validate_image_upload_rejects_truncated_image(
    fmt: str, save_kwargs: dict[str, object]
) -> None:
    """Verify a truncated upload of every allowed format is rejected."""
    # Given a noisy image cut to 90% of its bytes
    img = Image.effect_noise((256, 256), 64).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format=fmt, **save_kwargs)
    data = buf.getvalue()

    # When/Then validation raises ValidationError
    with pytest.raises(ValidationError):
        validate_image_upload(data=data[: len(data) * 9 // 10])


# Decode memory budgets. Pillow can only downscale JPEG while decoding, so a PNG, GIF, or WEBP
# avatar is decoded at full size once (about 4 bytes per pixel for RGB PNG, about 16 for WEBP,
# whose decoder keeps extra canvases). The budgets cover everything beyond that:
# - The avatar pipeline adds at most 48 x (512 x 512 x 4) bytes on top of that one decode.
# - Asset validation never decodes a PNG or WEBP raster and stays under 32 MiB for them.
_MIB = 1024 * 1024
AVATAR_OVERHEAD_BUDGET = 48 * AVATAR_SIZE * AVATAR_SIZE * 4
ASSET_VALIDATION_BUDGET = 32 * _MIB

# Run in a fresh interpreter so the peak RSS high-water mark covers one decode and nothing else.
_MEASURE_SCRIPT = """
import io, json, resource, sys
from PIL import Image
from vapi.utils import images

mode, path = sys.argv[1], sys.argv[2]
with open(path, "rb") as f:
    data = f.read()

def peak():
    unit = 1 if sys.platform == "darwin" else 1024  # ru_maxrss is bytes on macOS, KiB on Linux
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * unit

before = peak()
if mode == "decode":
    with Image.open(io.BytesIO(data)) as img:
        img.load()
elif mode == "avatar":
    images.normalize_avatar(data)
else:
    images.validate_image_upload(data=data)
print(json.dumps({"peak_bytes": peak() - before}))
"""


def _measure_peak(mode: str, path: str) -> int:
    """Return the peak RSS growth, in bytes, of one decode run in a fresh interpreter."""
    proc = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _MEASURE_SCRIPT, mode, path],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(proc.stdout.strip().splitlines()[-1])["peak_bytes"]


@pytest.fixture(scope="module")
def near_cap_images(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    """Write a lossless WEBP and a PNG just under the pixel cap; both compress to a few KB."""
    side = int(MAX_IMAGE_PIXELS**0.5)
    directory = tmp_path_factory.mktemp("near_cap")
    paths = {}
    img = Image.new("RGB", (side, side), (20, 40, 60))
    for fmt, kwargs in (("WEBP", {"lossless": True}), ("PNG", {})):
        path = directory / f"near_cap.{fmt.lower()}"
        img.save(path, format=fmt, **kwargs)
        paths[fmt] = str(path)
    return paths


@pytest.mark.parametrize("fmt", ["WEBP", "PNG"])
def test_normalize_avatar_peak_memory_stays_within_budget(
    near_cap_images: dict[str, str], fmt: str
) -> None:
    """Verify the avatar pipeline adds no full-size copies on top of the one unavoidable decode."""
    # Given a lossless WEBP or PNG just under the pixel cap
    path = near_cap_images[fmt]

    # When measuring a bare decode and a full avatar normalization of the same file
    decode_peak = _measure_peak("decode", path)
    avatar_peak = _measure_peak("avatar", path)

    # Then normalization stays within the fixed budget above the bare decode
    assert avatar_peak - decode_peak < AVATAR_OVERHEAD_BUDGET, (
        f"{fmt}: avatar {avatar_peak / _MIB:.1f} MiB vs decode {decode_peak / _MIB:.1f} MiB"
    )


@pytest.mark.parametrize("fmt", ["WEBP", "PNG"])
def test_validate_image_upload_peak_memory_stays_within_budget(
    near_cap_images: dict[str, str], fmt: str
) -> None:
    """Verify asset validation checks integrity without decoding the full raster."""
    # Given a lossless WEBP or PNG just under the pixel cap
    path = near_cap_images[fmt]

    # When validating the upload
    peak = _measure_peak("asset", path)

    # Then validation stays within the fixed budget
    assert peak < ASSET_VALIDATION_BUDGET, f"{fmt}: asset validation {peak / _MIB:.1f} MiB"
