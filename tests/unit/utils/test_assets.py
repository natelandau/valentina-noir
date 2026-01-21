"""Test the assets module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.constants import S3AssetParentType, S3AssetType
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
    @pytest.mark.no_clean_db
    def test_sanitize_filename_basic(self, filename: str, expected: str) -> None:
        """Verify filename sanitization removes dangerous characters."""
        assert assets.sanitize_filename(filename) == expected

    @pytest.mark.no_clean_db
    def test_sanitize_filename_long_filename_without_extension(self) -> None:
        """Verify long filenames without extension are truncated to max length."""
        # Given: A filename exceeding 200 characters
        long_name = "a" * 250

        # When: Sanitizing the filename
        result = assets.sanitize_filename(long_name)

        # Then: Filename is truncated to 200 characters
        assert len(result) == 200
        assert result == "a" * 200

    @pytest.mark.no_clean_db
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

    @pytest.mark.no_clean_db
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


class TestDetermineS3AssetType:
    """Tests for determine_asset_type function."""

    @pytest.mark.parametrize(
        ("mime_type", "expected"),
        [
            # Image types
            ("image/jpeg", S3AssetType.IMAGE),
            ("image/png", S3AssetType.IMAGE),
            ("image/gif", S3AssetType.IMAGE),
            ("image/webp", S3AssetType.IMAGE),
            ("image/svg+xml", S3AssetType.IMAGE),
            ("IMAGE/JPEG", S3AssetType.IMAGE),
            # Audio types
            ("audio/mpeg", S3AssetType.AUDIO),
            ("audio/wav", S3AssetType.AUDIO),
            ("audio/ogg", S3AssetType.AUDIO),
            ("AUDIO/MP3", S3AssetType.AUDIO),
            # Video types
            ("video/mp4", S3AssetType.VIDEO),
            ("video/webm", S3AssetType.VIDEO),
            ("video/quicktime", S3AssetType.VIDEO),
            ("VIDEO/AVI", S3AssetType.VIDEO),
            # Text types
            ("text/plain", S3AssetType.TEXT),
            ("text/html", S3AssetType.TEXT),
            ("text/css", S3AssetType.TEXT),
            ("TEXT/MARKDOWN", S3AssetType.TEXT),
        ],
    )
    @pytest.mark.no_clean_db
    def test_determine_asset_type_by_prefix(self, mime_type: str, expected: S3AssetType) -> None:
        """Verify asset type is determined by MIME type prefix."""
        assert assets.determine_asset_type(mime_type) == expected

    @pytest.mark.parametrize(
        ("mime_type", "expected"),
        [
            # PDF documents
            ("application/pdf", S3AssetType.DOCUMENT),
            # Microsoft Office formats
            ("application/msword", S3AssetType.DOCUMENT),
            ("application/vnd.ms-excel", S3AssetType.DOCUMENT),
            ("application/vnd.ms-powerpoint", S3AssetType.DOCUMENT),
            # OpenDocument formats
            ("application/vnd.oasis.opendocument.text", S3AssetType.DOCUMENT),
            ("application/vnd.oasis.opendocument.spreadsheet", S3AssetType.DOCUMENT),
            ("application/vnd.oasis.opendocument.presentation", S3AssetType.DOCUMENT),
            # Modern Office formats
            (
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                S3AssetType.DOCUMENT,
            ),
            (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                S3AssetType.DOCUMENT,
            ),
        ],
    )
    @pytest.mark.no_clean_db
    def test_determine_asset_type_documents(self, mime_type: str, expected: S3AssetType) -> None:
        """Verify document MIME types are correctly identified."""
        assert assets.determine_asset_type(mime_type) == expected

    @pytest.mark.parametrize(
        ("mime_type", "expected"),
        [
            ("application/zip", S3AssetType.ARCHIVE),
            ("application/x-tar", S3AssetType.ARCHIVE),
            ("application/gzip", S3AssetType.ARCHIVE),
            ("application/x-rar-compressed", S3AssetType.ARCHIVE),
            ("application/x-7z-compressed", S3AssetType.ARCHIVE),
        ],
    )
    @pytest.mark.no_clean_db
    def test_determine_asset_type_archives(self, mime_type: str, expected: S3AssetType) -> None:
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
    @pytest.mark.no_clean_db
    def test_determine_asset_type_other(self, mime_type: str) -> None:
        """Verify unrecognized MIME types return OTHER."""
        assert assets.determine_asset_type(mime_type) == S3AssetType.OTHER


class TestDetermineParentType:
    """Tests for determine_parent_type function."""

    @pytest.mark.parametrize(("expected"), S3AssetParentType)
    async def test_determine_parent_type(
        self,
        expected: S3AssetParentType,
        company_factory: Callable[..., Company],
        character_factory: Callable[..., Character],
        user_factory: Callable[..., User],
        campaign_factory: Callable[..., Campaign],
        campaign_book_factory: Callable[..., CampaignBook],
        campaign_chapter_factory: Callable[..., CampaignChapter],
    ) -> None:
        """Verify parent type is determined correctly."""
        match expected:
            case S3AssetParentType.CHARACTER:
                parent = await character_factory()
            case S3AssetParentType.USER:
                parent = await user_factory()
            case S3AssetParentType.CAMPAIGN:
                parent = await campaign_factory()
            case S3AssetParentType.CAMPAIGN_BOOK:
                parent = await campaign_book_factory()
            case S3AssetParentType.CAMPAIGN_CHAPTER:
                parent = await campaign_chapter_factory()
            case S3AssetParentType.COMPANY:
                parent = await company_factory()
            case _:
                parent = None

        assert assets.determine_parent_type(parent=parent) == expected

    async def test_determine_parent_type_unknown(
        self,
        s3asset_factory: Callable[..., S3Asset],
    ) -> None:
        """Verify parent type is determined to UNKNOWN when parent database model is not in the S3AssetParentType enum."""
        # Given: An S3Asset object
        # We choose this object, b/c there is no scenario where an S3Asset will have an asset uploaded to it
        s3_asset = await s3asset_factory()

        # When: Determining the parent type
        assert assets.determine_parent_type(parent=s3_asset) == S3AssetParentType.UNKNOWN


class TestAddAssetToParent:
    """Tests for add_asset_to_parent function."""

    async def test_add_asset_to_parent(
        self, s3asset_factory: Callable[..., S3Asset], character_factory: Callable[..., Character]
    ) -> None:
        """Verify asset is added to parent correctly."""
        # Given objects
        character = await character_factory(asset_ids=[])
        s3_asset = await s3asset_factory(
            parent_type=S3AssetParentType.CHARACTER, parent_id=character.id
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
        s3_asset = await s3asset_factory(parent_type=S3AssetParentType.UNKNOWN, parent_id=None)

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
            parent_type=S3AssetParentType.CHARACTER, parent_id=character.id
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
        s3_asset = await s3asset_factory(parent_type=S3AssetParentType.UNKNOWN, parent_id=None)

        # When: Removing the asset from the parent
        result = await assets.remove_asset_from_parent(asset=s3_asset)

        # Then: Asset is not removed from the parent
        assert result is None
