"""Image upload validation and avatar normalization utilities."""

import io
import struct

from PIL import Image, ImageOps, UnidentifiedImageError

from vapi.constants import ALLOWED_IMAGE_UPLOAD_FORMATS
from vapi.lib.exceptions import ValidationError

__all__ = (
    "AVATAR_SIZE",
    "MAX_UPLOAD_BYTES",
    "normalize_avatar",
    "validate_image_upload",
)

# Reject decompression bombs: refuse to decode images above this pixel count.
Image.MAX_IMAGE_PIXELS = 24_000_000  # ~24 MP

AVATAR_SIZE = 512
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
_ALLOWED_FORMATS = frozenset(ALLOWED_IMAGE_UPLOAD_FORMATS)
_WEBP_QUALITY = 85

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


def _invalid(message: str) -> ValidationError:
    """Build a ValidationError for a rejected avatar upload."""
    return ValidationError(
        detail=message,
        invalid_parameters=[{"field": "upload", "message": message}],
    )


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
            img.verify()  # Parse the full stream to confirm a valid, non-bomb raster image.
    except _DECODE_ERRORS as e:
        msg = "Upload must be a PNG, JPEG, GIF, or WEBP image."
        raise _invalid(msg) from e

    mime_type = ALLOWED_IMAGE_UPLOAD_FORMATS.get(detected_format or "")
    if mime_type is None:
        msg = "Upload must be a PNG, JPEG, GIF, or WEBP image."
        raise _invalid(msg)
    return mime_type
