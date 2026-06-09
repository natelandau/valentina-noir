"""Avatar image normalization utilities."""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

from vapi.lib.exceptions import ValidationError

__all__ = ("AVATAR_SIZE", "MAX_UPLOAD_BYTES", "normalize_avatar")

# Reject decompression bombs: refuse to decode images above this pixel count.
Image.MAX_IMAGE_PIXELS = 24_000_000  # ~24 MP

AVATAR_SIZE = 512
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
_ALLOWED_FORMATS = frozenset({"PNG", "JPEG", "WEBP", "GIF"})
_WEBP_QUALITY = 85


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
    except (UnidentifiedImageError, OSError, ValueError) as e:
        msg = "Avatar image could not be read."
        raise _invalid(msg) from e
