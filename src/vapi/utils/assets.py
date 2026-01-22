"""Asset utilities."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

from vapi.constants import S3AssetParentType, S3AssetType
from vapi.db.models import Campaign, CampaignBook, CampaignChapter, Character, Company, User

if TYPE_CHECKING:
    from vapi.db.models.aws import S3Asset
    from vapi.db.models.base import BaseDocument

__all__ = (
    "add_asset_to_parent",
    "determine_asset_type",
    "determine_parent_type",
    "remove_asset_from_parent",
    "sanitize_filename",
)

PARENT_MODEL_MAP: dict[S3AssetParentType, type[BaseDocument]] = {
    S3AssetParentType.CHARACTER: Character,
    S3AssetParentType.CAMPAIGN: Campaign,
    S3AssetParentType.CAMPAIGN_BOOK: CampaignBook,
    S3AssetParentType.CAMPAIGN_CHAPTER: CampaignChapter,
    S3AssetParentType.USER: User,
    S3AssetParentType.COMPANY: Company,
}

# Exhaustiveness check - fails fast if enum gains new values
_expected: set[S3AssetParentType] = {
    pt for pt in S3AssetParentType if pt != S3AssetParentType.UNKNOWN
}
if _missing := _expected - set(PARENT_MODEL_MAP.keys()):  # pragma: no cover
    msg = f"parent_model_map missing mappings: {_missing}"
    raise RuntimeError(msg)
del _expected, _missing


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


def determine_asset_type(mime_type: str) -> S3AssetType:  # noqa: PLR0911
    """Determine asset type from MIME type.

    Args:
        mime_type: MIME type string (e.g., "image/jpeg", "audio/mpeg")

    Returns:
        The corresponding S3AssetType
    """
    mime_prefix = mime_type.split("/")[0].lower()

    match mime_prefix:
        case "image":
            return S3AssetType.IMAGE
        case "audio":
            return S3AssetType.AUDIO
        case "text":
            return S3AssetType.TEXT
        case "video":
            return S3AssetType.VIDEO
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
                return S3AssetType.DOCUMENT
            if any(
                archive_type in mime_lower
                for archive_type in ["zip", "tar", "gzip", "rar", "7z", "compressed"]
            ):
                return S3AssetType.ARCHIVE
            return S3AssetType.OTHER


def determine_parent_type(
    *,
    parent: BaseDocument | None = None,
) -> S3AssetParentType:
    """Determine parent type from parent object.

    Args:
        parent: Parent object.

    Returns:
        The corresponding S3AssetParentType
    """
    if not parent:
        return S3AssetParentType.UNKNOWN

    try:
        return S3AssetParentType(parent.__class__.__name__.lower())
    except ValueError:
        return S3AssetParentType.UNKNOWN


async def add_asset_to_parent(asset: S3Asset) -> None:
    """Add an asset to a parent document's list of assets.

    Args:
        asset: The asset to add.
    """
    if asset.parent_type == S3AssetParentType.UNKNOWN:
        return

    model_class = PARENT_MODEL_MAP.get(asset.parent_type)
    if model_class is None:  # pragma: no cover
        return

    parent = await model_class.get(asset.parent_id)
    if parent and hasattr(parent, "asset_ids") and asset.id not in parent.asset_ids:
        parent.asset_ids.append(asset.id)
        await parent.save()


async def remove_asset_from_parent(asset: S3Asset) -> None:
    """Remove an asset from a parent document's list of assets.

    Args:
        asset: The asset to remove.
    """
    if asset.parent_type == S3AssetParentType.UNKNOWN:
        return

    model_class = PARENT_MODEL_MAP.get(asset.parent_type)
    if model_class is None:  # pragma: no cover
        return

    parent = await model_class.get(asset.parent_id)
    if parent and hasattr(parent, "asset_ids"):
        parent.asset_ids = [x for x in parent.asset_ids if x != asset.id]
        await parent.save()
