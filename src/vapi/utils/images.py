"""Image upload validation and avatar normalization utilities."""

import asyncio
import contextvars
import functools
import io
import struct
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from PIL import ExifTags, Image, UnidentifiedImageError

from vapi.constants import ALLOWED_IMAGE_UPLOAD_FORMATS
from vapi.lib.exceptions import ValidationError

__all__ = (
    "AVATAR_SIZE",
    "MAX_IMAGE_PIXELS",
    "MAX_UPLOAD_BYTES",
    "normalize_avatar",
    "run_image_decode",
    "validate_image_upload",
)

# Reject decompression bombs: refuse to decode images above this pixel count. Pillow only
# warns between 1x and 2x its own limit, so _check_pixel_budget enforces the cap explicitly.
MAX_IMAGE_PIXELS = 24_000_000  # ~24 MP
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

AVATAR_SIZE = 512
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
_ALLOWED_FORMATS = frozenset(ALLOWED_IMAGE_UPLOAD_FORMATS)
_WEBP_QUALITY = 85

# Pillow can only downscale JPEG while decoding, so other formats are shrunk in bands of about
# this many RGBA bytes instead of being converted or rotated as one full-size copy.
_BAND_BYTES = 4 * 1024 * 1024

_ORIENTATION_TRANSPOSE = {
    2: Image.Transpose.FLIP_LEFT_RIGHT,
    3: Image.Transpose.ROTATE_180,
    4: Image.Transpose.FLIP_TOP_BOTTOM,
    5: Image.Transpose.TRANSPOSE,
    6: Image.Transpose.ROTATE_270,
    7: Image.Transpose.TRANSVERSE,
    8: Image.Transpose.ROTATE_90,
}

# Formats whose truncation is caught without decoding pixels: PNG's verify() checks every chunk
# CRC through IEND, and a truncated WEBP fails to open. Neither check inspects the compressed
# image stream, so a crafted file with valid framing but a broken stream is stored as uploaded.
_STRUCTURE_CHECKED_FORMATS = frozenset({"PNG", "WEBP"})

# A tiny upload can declare a raster that takes hundreds of MB to decode, so decodes run on
# their own small pool: a burst of uploads queues instead of decoding all at once.
MAX_CONCURRENT_IMAGE_DECODES = 2
_DECODE_EXECUTOR = ThreadPoolExecutor(
    max_workers=MAX_CONCURRENT_IMAGE_DECODES, thread_name_prefix="image-decode"
)

# Pillow raises a wide spread of exception types from open()/verify()/decode on
# malformed input: format plugins surface SyntaxError, EOFError, and struct.error
# in addition to the documented OSError/ValueError, and the bomb guard raises a
# DecompressionBombWarning (escalated to an exception when warnings are errors).
# Treat any of them as "not a usable image" so untrusted bytes never crash the
# request with an unhandled 500.
_DECODE_ERRORS = (
    UnidentifiedImageError,
    OSError,
    ValueError,
    EOFError,
    SyntaxError,
    struct.error,
    Image.DecompressionBombError,
    Image.DecompressionBombWarning,
)


async def run_image_decode[T](func: Callable[..., T], /, *args: object, **kwargs: object) -> T:
    """Run a Pillow decode off the event loop with bounded concurrency.

    Use this instead of ``asyncio.to_thread`` for any function that decodes untrusted image
    bytes, so concurrent uploads cannot multiply decode memory across the default pool.

    Args:
        func: The blocking decode function to run.
        *args: Positional arguments for ``func``.
        **kwargs: Keyword arguments for ``func``.

    Returns:
        The return value of ``func``.
    """
    loop = asyncio.get_running_loop()
    call = functools.partial(contextvars.copy_context().run, func, *args, **kwargs)
    return await loop.run_in_executor(_DECODE_EXECUTOR, call)


def _invalid(message: str) -> ValidationError:
    """Build a ValidationError for a rejected avatar upload."""
    return ValidationError(
        detail=message,
        invalid_parameters=[{"field": "upload", "message": message}],
    )


def _check_pixel_budget(img: Image.Image, message: str) -> None:
    """Reject an opened image whose dimensions exceed the pixel budget, before decoding it."""
    if img.width * img.height > MAX_IMAGE_PIXELS:
        raise _invalid(message)


def _reduce_center_square(img: Image.Image) -> Image.Image:
    """Center-crop an image to a square, box-reduced to between 2x and 4x the avatar size, in RGBA.

    The source is processed in horizontal bands, so beyond the decoded source only one band and
    the reduced output are ever held in memory. Box reduction is exact per band, so the result
    matches reducing the whole square at once.
    """
    side = min(img.size)
    factor = max(1, side // (AVATAR_SIZE * 2))
    side -= side % factor
    left = (img.width - side) // 2
    top = (img.height - side) // 2
    band_rows = max(factor, _BAND_BYTES // (side * 4) // factor * factor)

    out = Image.new("RGBA", (side // factor, side // factor))
    for y in range(0, side, band_rows):
        rows = min(band_rows, side - y)
        band = img.crop((left, top + y, left + side, top + y + rows)).convert("RGBA")
        out.paste(band.reduce(factor), (0, y // factor))
    return out


def normalize_avatar(data: bytes) -> bytes:
    """Validate and normalize an uploaded avatar to a 512x512 WebP image.

    Enforce the upload size cap, accept only PNG/JPEG/WEBP/GIF, take the first
    frame of animated images, apply then strip EXIF orientation (dropping GPS and
    camera metadata), center-crop to a square, resize to 512x512, and re-encode to
    WebP. Use this for any user-supplied avatar so stored avatars are always a
    uniform, metadata-free, statically-sized image.

    Args:
        data: Raw uploaded image bytes.

    Returns:
        WebP-encoded bytes of the normalized 512x512 avatar.

    Raises:
        ValidationError: If the payload exceeds the size cap, is not a decodable
            image, or is not an allowed format.
    """
    if len(data) > MAX_UPLOAD_BYTES:
        msg = "Avatar image must be 5 MB or smaller."
        raise _invalid(msg)

    try:
        with Image.open(io.BytesIO(data)) as src:
            if src.format not in _ALLOWED_FORMATS:
                msg = "Avatar must be a PNG, JPEG, WEBP, or GIF image."
                raise _invalid(msg)
            _check_pixel_budget(src, "Avatar image is too large.")

            if src.format == "JPEG":
                # Let the decoder scale down by up to 8x, which cuts decode memory for the
                # common case of a large photo while keeping enough pixels for the resize.
                src.draft("RGB", (AVATAR_SIZE * 2, AVATAR_SIZE * 2))
            src.seek(0)  # First frame only; flattens animated GIFs.
            orientation = src.getexif().get(ExifTags.Base.Orientation)
            img = _reduce_center_square(src)

        # A centered square crop and a square resize both commute with every EXIF orientation
        # (to within a pixel of crop offset), so the small final square is the one rotated.
        # The new image carries no EXIF or metadata.
        img = img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
        if transpose := _ORIENTATION_TRANSPOSE.get(orientation):
            img = img.transpose(transpose)

        out = io.BytesIO()
        img.save(out, format="WEBP", quality=_WEBP_QUALITY)
        return out.getvalue()
    except _DECODE_ERRORS as e:
        msg = "Avatar image could not be read."
        raise _invalid(msg) from e


def validate_image_upload(*, data: bytes) -> str:
    """Validate that uploaded bytes are an allowed image and return their canonical MIME type.

    Open the bytes with Pillow, confirm the detected format is one of the allowed
    upload formats (PNG/JPEG/GIF/WEBP), and return the canonical MIME type for that
    format. The client-declared content type is deliberately ignored: the returned
    value comes from the bytes themselves, so a caller can store a trustworthy MIME
    type that cannot be spoofed (e.g. HTML or SVG mislabeled as image/png). Non-image
    payloads, rasters over the pixel budget, and truncated files are rejected; PNG and
    WEBP are checked structurally without decoding pixels, while JPEG and GIF are
    decoded. Call this before persisting any user-supplied asset so only verified
    images reach S3.

    Args:
        data: Raw uploaded file bytes.

    Returns:
        The canonical MIME type of the detected image format (e.g. "image/png").

    Raises:
        ValidationError: If the bytes are not a decodable image, are not one of the
            allowed formats, or exceed the decompression-bomb pixel guard.
    """
    try:
        with Image.open(io.BytesIO(data)) as img:
            detected_format = img.format
            _check_pixel_budget(img, "Upload image is too large.")
            img.verify()  # Check stream structure and checksums
        if detected_format not in _STRUCTURE_CHECKED_FORMATS:
            # verify() leaves the image unusable and skips pixel data, so decode a fresh copy to
            # reject truncated rasters. draft() decodes JPEG at 1/8 scale and is a no-op elsewhere.
            with Image.open(io.BytesIO(data)) as img:
                img.draft(img.mode, (1, 1))
                img.load()
    except _DECODE_ERRORS as e:
        msg = "Upload must be a PNG, JPEG, GIF, or WEBP image."
        raise _invalid(msg) from e

    mime_type = ALLOWED_IMAGE_UPLOAD_FORMATS.get(detected_format or "")
    if mime_type is None:
        msg = "Upload must be a PNG, JPEG, GIF, or WEBP image."
        raise _invalid(msg)
    return mime_type
