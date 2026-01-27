"""Test the assets module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.constants import AssetParentType, AssetType
from vapi.utils import assets

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.models import (
        Campaign,
        CampaignBook,
        CampaignChapter,
        Character,
        Company,
        S3Asset,
        User,
    )

pytestmark = pytest.mark.anyio


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            # Normal filenames
            ("File.txt", "File.txt"),
            ("my_document.pdf", "my_document.pdf"),
            ("image.jpg", "image.jpg"),
            # Filenames with dangerous characters - HTTP header injection
            ("file\r\n.txt", "file.txt"),
            ('file"name.txt', "filename.txt"),
            ("file'name.txt", "filename.txt"),
            ("file;name.txt", "filename.txt"),
            ("file:name.txt", "filename.txt"),
            # Path traversal attempts - Path().name extracts final component
            ("../../../etc/passwd", "passwd"),
            ("file/../name.txt", "name.txt"),
            ("/path/to/file.txt", "file.txt"),
            # Windows-style backslashes are stripped (not path separators on POSIX)
            ("C:\\Users\\file.txt", "CUsersfile.txt"),
            ("..\\..\\system32", "system32"),
            # Control characters
            ("file\x00name.txt", "filename.txt"),
            ("file\x1fname.txt", "filename.txt"),
            ("file\x7fname.txt", "filename.txt"),
            # Special character replacements
            ("file&name.txt", "fileandname.txt"),
            ("file%name.txt", "filename.txt"),
            ("file|name.txt", "file-name.txt"),
            ("file<name>.txt", "filename.txt"),
            # Whitespace handling
            ("  file.txt  ", "file.txt"),
            # Empty or minimal after sanitization
            ("...", "."),  # ".." removed, leaving single "."
            ("..", "upload"),  # ".." removed entirely
            ("", "upload"),
            ("   ", "upload"),
        ],
    )
    def test_sanitize_filename_basic(self, filename: str, expected: str) -> None:
        """Verify filename sanitization removes dangerous characters."""
        assert assets.sanitize_filename(filename) == expected

    def test_sanitize_filename_long_filename_without_extension(self) -> None:
        """Verify long filenames without extension are truncated to max length."""
        # Given: A filename exceeding 200 characters
        long_name = "a" * 250

        # When: Sanitizing the filename
        result = assets.sanitize_filename(long_name)

        # Then: Filename is truncated to 200 characters
        assert len(result) == 200
        assert result == "a" * 200

    def test_sanitize_filename_long_filename_with_extension(self) -> None:
        """Verify long filenames preserve extension when truncated."""
        # Given: A filename with extension exceeding 200 characters
        long_name = "a" * 250 + ".pdf"

        # When: Sanitizing the filename
        result = assets.sanitize_filename(long_name)

        # Then: Filename is truncated but extension is preserved
        # max_length(200) - len("pdf")(3) - 1 = 196 chars for name + "." + "pdf"
        assert len(result) == 200
        assert result.endswith(".pdf")
        assert result == "a" * 196 + ".pdf"

    def test_sanitize_filename_combined_dangerous_patterns(self) -> None:
        """Verify multiple dangerous patterns are all sanitized."""
        # Given: A filename with multiple dangerous patterns
        dangerous = "../path\r\nfile;name<script>.txt"

        # When: Sanitizing the filename
        result = assets.sanitize_filename(dangerous)

        # Then: All dangerous patterns are removed
        assert ".." not in result
        assert "\r" not in result
        assert "\n" not in result
        assert ";" not in result
        assert "<" not in result
        assert ">" not in result


class TestDetermineAssetType:
    """Tests for determine_asset_type function."""

    @pytest.mark.parametrize(
        ("mime_type", "expected"),
        [
            # Image types
            ("image/jpeg", AssetType.IMAGE),
            ("image/png", AssetType.IMAGE),
            ("image/gif", AssetType.IMAGE),
            ("image/webp", AssetType.IMAGE),
            ("image/svg+xml", AssetType.IMAGE),
            ("IMAGE/JPEG", AssetType.IMAGE),
            # Audio types
            ("audio/mpeg", AssetType.AUDIO),
            ("audio/wav", AssetType.AUDIO),
            ("audio/ogg", AssetType.AUDIO),
            ("AUDIO/MP3", AssetType.AUDIO),
            # Video types
            ("video/mp4", AssetType.VIDEO),
            ("video/webm", AssetType.VIDEO),
            ("video/quicktime", AssetType.VIDEO),
            ("VIDEO/AVI", AssetType.VIDEO),
            # Text types
            ("text/plain", AssetType.TEXT),
            ("text/html", AssetType.TEXT),
            ("text/css", AssetType.TEXT),
            ("TEXT/MARKDOWN", AssetType.TEXT),
        ],
    )
    def test_determine_asset_type_by_prefix(self, mime_type: str, expected: AssetType) -> None:
        """Verify asset type is determined by MIME type prefix."""
        assert assets.determine_asset_type(mime_type) == expected

    @pytest.mark.parametrize(
        ("mime_type", "expected"),
        [
            # PDF documents
            ("application/pdf", AssetType.DOCUMENT),
            # Microsoft Office formats
            ("application/msword", AssetType.DOCUMENT),
            ("application/vnd.ms-excel", AssetType.DOCUMENT),
            ("application/vnd.ms-powerpoint", AssetType.DOCUMENT),
            # OpenDocument formats
            ("application/vnd.oasis.opendocument.text", AssetType.DOCUMENT),
            ("application/vnd.oasis.opendocument.spreadsheet", AssetType.DOCUMENT),
            ("application/vnd.oasis.opendocument.presentation", AssetType.DOCUMENT),
            # Modern Office formats
            (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                AssetType.DOCUMENT,
            ),
            (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                AssetType.DOCUMENT,
            ),
        ],
    )
    def test_determine_asset_type_documents(self, mime_type: str, expected: AssetType) -> None:
        """Verify document MIME types are correctly identified."""
        assert assets.determine_asset_type(mime_type) == expected

    @pytest.mark.parametrize(
        ("mime_type", "expected"),
        [
            ("application/zip", AssetType.ARCHIVE),
            ("application/x-tar", AssetType.ARCHIVE),
            ("application/gzip", AssetType.ARCHIVE),
            ("application/x-rar-compressed", AssetType.ARCHIVE),
            ("application/x-7z-compressed", AssetType.ARCHIVE),
        ],
    )
    def test_determine_asset_type_archives(self, mime_type: str, expected: AssetType) -> None:
        """Verify archive MIME types are correctly identified."""
        assert assets.determine_asset_type(mime_type) == expected

    @pytest.mark.parametrize(
        "mime_type",
        [
            "application/octet-stream",
            "application/json",
            "application/xml",
            "application/unknown",
        ],
    )
    def test_determine_asset_type_other(self, mime_type: str) -> None:
        """Verify unrecognized MIME types return OTHER."""
        assert assets.determine_asset_type(mime_type) == AssetType.OTHER


class TestDetermineParentType:
    """Tests for determine_parent_type function."""

    @pytest.mark.parametrize(("expected"), AssetParentType)
    async def test_determine_parent_type(
        self,
        expected: AssetParentType,
        company_factory: Callable[..., Company],
        character_factory: Callable[..., Character],
        user_factory: Callable[..., User],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        campaign_chapter_factory: Callable[..., CampaignChapter],
    ) -> None:
        """Verify parent type is determined correctly."""
        match expected:
            case AssetParentType.CHARACTER:
                parent = await character_factory()
            case AssetParentType.USER:
                parent = await user_factory()
            case AssetParentType.CAMPAIGN:
                parent = await campaign_factory()
            case AssetParentType.CAMPAIGN_BOOK:
                parent = await campaign_book_factory()
            case AssetParentType.CAMPAIGN_CHAPTER:
                parent = await campaign_chapter_factory()
            case AssetParentType.COMPANY:
                parent = await company_factory()
            case _:
                parent = None

        assert assets.determine_parent_type(parent=parent) == expected

    async def test_determine_parent_type_unknown(
        self,
        s3asset_factory: Callable[..., S3Asset],
    ) -> None:
        """Verify parent type is determined to UNKNOWN when parent database model is not in the AssetParentType enum."""
        # Given: An S3Asset object
        # We choose this object, b/c there is no scenario where an S3Asset will have an asset uploaded to it
        s3_asset = await s3asset_factory()

        # When: Determining the parent type
        assert assets.determine_parent_type(parent=s3_asset) == AssetParentType.UNKNOWN


class TestAddAssetToParent:
    """Tests for add_asset_to_parent function."""

    async def test_add_asset_to_parent(
        self, s3asset_factory: Callable[..., S3Asset], character_factory: Callable[..., Character]
    ) -> None:
        """Verify asset is added to parent correctly."""
        # Given objects
        character = await character_factory(asset_ids=[])
        s3_asset = await s3asset_factory(
            parent_type=AssetParentType.CHARACTER, parent_id=character.id
        )

        # When: Adding the asset to the parent
        await assets.add_asset_to_parent(asset=s3_asset)

        # Then: Asset is added to the parent
        await character.sync()
        assert character.asset_ids == [s3_asset.id]

    async def test_add_asset_to_parent_no_parent(
        self, s3asset_factory: Callable[..., S3Asset]
    ) -> None:
        """Verify add_asset_to_parent raises AttributeError when parent is None."""
        # Given: An S3Asset object
        s3_asset = await s3asset_factory(parent_type=AssetParentType.UNKNOWN, parent_id=None)

        # When: Adding the asset to the parent
        result = await assets.add_asset_to_parent(asset=s3_asset)

        # Then: Asset is not added to the parent
        assert result is None


class TestRemoveAssetFromParent:
    """Tests for remove_asset_from_parent function."""

    async def test_remove_asset_from_parent(
        self, s3asset_factory: Callable[..., S3Asset], character_factory: Callable[..., Character]
    ) -> None:
        """Verify asset is removed from parent correctly."""
        # Given objects
        character = await character_factory(asset_ids=[])
        s3_asset = await s3asset_factory(
            parent_type=AssetParentType.CHARACTER, parent_id=character.id
        )
        character.asset_ids.append(s3_asset.id)
        await character.save()

        # When: Removing the asset from the parent
        await assets.remove_asset_from_parent(asset=s3_asset)

        # Then: Asset is removed from the parent
        await character.sync()
        assert character.asset_ids == []

    async def test_remove_asset_from_parent_no_parent(
        self, s3asset_factory: Callable[..., S3Asset]
    ) -> None:
        """Verify remove_asset_from_parent returns None when parent is None."""
        # Given: An S3Asset object
        s3_asset = await s3asset_factory(parent_type=AssetParentType.UNKNOWN, parent_id=None)

        # When: Removing the asset from the parent
        result = await assets.remove_asset_from_parent(asset=s3_asset)

        # Then: Asset is not removed from the parent
        assert result is None
