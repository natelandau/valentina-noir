"""Asset utilities."""

import re
import unicodedata
from pathlib import Path

from vapi.constants import AssetType

__all__ = (
    "determine_asset_type",
    "sanitize_filename",
)


def sanitize_filename(filename: str) -> str:
    """Normalize an uploaded filename into a URL-safe, ASCII-only slug.

    Transliterates Unicode to ASCII, lowercases, replaces whitespace and
    underscores with hyphens, and strips everything except alphanumerics,
    hyphens, and dots. The result is safe for S3 metadata, Content-Disposition
    headers, and filesystem storage.

    Args:
        filename: Original filename to sanitize.

    Returns:
        Sanitized filename safe for S3 metadata and HTTP headers.
    """
    path = Path(Path(filename).name)
    stem = path.stem
    ext = path.suffix.lstrip(".").lower()

    stem = unicodedata.normalize("NFKD", stem).encode("ascii", errors="ignore").decode("ascii")
    stem = stem.lower()
    stem = re.sub(r"[\s_]+", "-", stem)
    stem = re.sub(r"[^a-z0-9-]", "", stem)
    stem = re.sub(r"-{2,}", "-", stem).strip("-")

    if not stem:
        stem = "upload"

    max_stem = 200 - len(ext) - 1 if ext else 200
    stem = stem[:max_stem].rstrip("-")

    return f"{stem}.{ext}" if ext else stem


def determine_asset_type(mime_type: str) -> AssetType:  # noqa: PLR0911
    """Determine asset type from MIME type.

    Args:
        mime_type: MIME type string (e.g., "image/jpeg", "audio/mpeg")

    Returns:
        The corresponding AssetType
    """
    mime_prefix = mime_type.split("/", maxsplit=1)[0].lower()

    match mime_prefix:
        case "image":
            return AssetType.IMAGE
        case "audio":
            return AssetType.AUDIO
        case "text":
            return AssetType.TEXT
        case "video":
            return AssetType.VIDEO
        case _:
            mime_lower = mime_type.lower()
            if any(
                doc_type in mime_lower
                for doc_type in [
                    "pdf",
                    "document",
                    "word",
                    "spreadsheet",
                    "sheet",
                    "presentation",
                    "text",
                    "msword",
                    "ms-excel",
                    "ms-powerpoint",
                ]
            ):
                return AssetType.DOCUMENT
            if any(
                archive_type in mime_lower
                for archive_type in ["zip", "tar", "gzip", "rar", "7z", "compressed"]
            ):
                return AssetType.ARCHIVE
            return AssetType.OTHER
