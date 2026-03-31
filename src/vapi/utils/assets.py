"""Asset utilities."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING

from vapi.constants import AssetParentType, AssetType
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

PARENT_MODEL_MAP: dict[AssetParentType, type[BaseDocument]] = {
    AssetParentType.CHARACTER: Character,
    AssetParentType.CAMPAIGN: Campaign,
    AssetParentType.CAMPAIGN_BOOK: CampaignBook,
    AssetParentType.CAMPAIGN_CHAPTER: CampaignChapter,
    AssetParentType.USER: User,
    AssetParentType.COMPANY: Company,
}

# Exhaustiveness check - fails fast if enum gains new values
_expected: set[AssetParentType] = {pt for pt in AssetParentType if pt != AssetParentType.UNKNOWN}
if _missing := _expected - set(PARENT_MODEL_MAP.keys()):  # pragma: no cover
    msg = f"parent_model_map missing mappings: {_missing}"
    raise RuntimeError(msg)
del _expected, _missing


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

    # Transliterate Unicode → ASCII (é→e, ñ→n, etc.)
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


def determine_parent_type(
    *,
    parent: BaseDocument | None = None,
) -> AssetParentType:
    """Determine parent type from parent object.

    Args:
        parent: Parent object.

    Returns:
        The corresponding AssetParentType
    """
    if not parent:
        return AssetParentType.UNKNOWN

    try:
        return AssetParentType(parent.__class__.__name__.lower())
    except ValueError:
        return AssetParentType.UNKNOWN


async def _get_asset_parent(asset: S3Asset) -> BaseDocument | None:
    """Look up the parent document for an asset, or None if not applicable."""
    if asset.parent_type == AssetParentType.UNKNOWN:
        return None

    model_class = PARENT_MODEL_MAP.get(asset.parent_type)
    if model_class is None:  # pragma: no cover
        return None

    parent = await model_class.get(asset.parent_id)
    return parent if parent and hasattr(parent, "asset_ids") else None


async def add_asset_to_parent(asset: S3Asset) -> None:
    """Add an asset to a parent document's list of assets.

    Args:
        asset: The asset to add.
    """
    parent = await _get_asset_parent(asset)
    if parent and asset.id not in parent.asset_ids:
        parent.asset_ids.append(asset.id)
        await parent.save()


async def remove_asset_from_parent(asset: S3Asset) -> None:
    """Remove an asset from a parent document's list of assets.

    Args:
        asset: The asset to remove.
    """
    parent = await _get_asset_parent(asset)
    if parent:
        parent.asset_ids = [x for x in parent.asset_ids if x != asset.id]
        await parent.save()
