"""Asset utilities."""

import re
from pathlib import Path

from vapi.constants import AssetType

__all__ = ("determine_asset_type", "sanitize_filename")


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for Content-Disposition header and general safety.

    Removes characters that could cause issues in HTTP headers, filesystems,
    or security vulnerabilities.

    Args:
        filename: Original filename to sanitize.

    Returns:
        Sanitized filename safe for Content-Disposition header.
    """
    # Get just the filename without path (security: prevent directory traversal)
    filename = Path(filename).name

    # Remove or replace dangerous characters
    # HTTP header injection
    filename = filename.replace("\r", "").replace("\n", "")
    filename = filename.replace('"', "").replace("'", "")
    filename = filename.replace(";", "").replace(":", "")

    # Path traversal attempts
    filename = filename.replace("..", "")
    filename = filename.replace("/", "").replace("\\", "")

    # Control characters (ASCII 0-31 and 127)
    filename = re.sub(r"[\x00-\x1f\x7f]", "", filename)

    # Optional: Replace problematic characters with safe alternatives
    filename = filename.replace("&", "and")
    filename = filename.replace("%", "")
    filename = filename.replace("|", "-")
    filename = filename.replace("<", "").replace(">", "")

    # Trim whitespace and limit length
    filename = filename.strip()

    # Ensure we still have a filename
    if not filename:
        filename = "upload"

    # Limit length (some systems have 255 char limits)
    max_length = 200  # Leave room for extension
    if len(filename) > max_length:
        # Preserve extension if present
        if "." in filename:
            name, ext = filename.rsplit(".", 1)
            filename = name[: max_length - len(ext) - 1] + "." + ext
        else:
            filename = filename[:max_length]

    return filename


def determine_asset_type(mime_type: str) -> AssetType:  # noqa: PLR0911
    """Determine asset type from MIME type.

    Args:
        mime_type: MIME type string (e.g., "image/jpeg", "audio/mpeg")

    Returns:
        The corresponding AssetType
    """
    mime_prefix = mime_type.split("/")[0].lower()

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
            # Handle document types by MIME suffix
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
