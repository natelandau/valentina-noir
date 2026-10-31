"""Image upload validation and avatar normalization utilities."""

import asyncio
import contextvars
import functools
import io
import struct
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageOps, UnidentifiedImageError

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
                # common case of a large photo while keeping enough pixels for the fit.
                src.draft("RGB", (AVATAR_SIZE * 2, AVATAR_SIZE * 2))
            src.seek(0)  # First frame only; flattens animated GIFs.
            img = ImageOps.exif_transpose(src)  # Honor orientation, then drop EXIF.
            img = img.convert("RGBA")
            img = ImageOps.fit(img, (AVATAR_SIZE, AVATAR_SIZE), method=Image.Resampling.LANCZOS)

            out = io.BytesIO()
            img.save(out, format="WEBP", quality=_WEBP_QUALITY)
            return out.getvalue()
    except _DECODE_ERRORS as e:
        msg = "Avatar image could not be read."
        raise _invalid(msg) from e


def validate_image_upload(*, data: bytes) -> str:
    """Validate that uploaded bytes are an allowed image and return their canonical MIME type.

    Decode the bytes with Pillow, confirm the detected format is one of the allowed
    upload formats (PNG/JPEG/GIF/WEBP), and return the canonical MIME type for that
    format. The client-declared content type is deliberately ignored: the returned
    value comes from the bytes themselves, so a caller can store a trustworthy MIME
    type that cannot be spoofed (e.g. HTML or SVG mislabeled as image/png). Decoding
    also rejects non-image payloads and trips Pillow's decompression-bomb guard. Call
    this before persisting any user-supplied asset so only verified images reach S3.

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
        # verify() leaves the image unusable and skips pixel data, so decode a fresh copy
        # to reject truncated or corrupt rasters
        with Image.open(io.BytesIO(data)) as img:
            img.load()
    except _DECODE_ERRORS as e:
        msg = "Upload must be a PNG, JPEG, GIF, or WEBP image."
        raise _invalid(msg) from e

    mime_type = ALLOWED_IMAGE_UPLOAD_FORMATS.get(detected_format or "")
    if mime_type is None:
        msg = "Upload must be a PNG, JPEG, GIF, or WEBP image."
        raise _invalid(msg)
    return mime_type
