"""Test the assets module."""

from __future__ import annotations

import pytest

from vapi.constants import AssetType
from vapi.utils import assets

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
    @pytest.mark.no_clean_db
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
    @pytest.mark.no_clean_db
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
    @pytest.mark.no_clean_db
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
    @pytest.mark.no_clean_db
    def test_determine_asset_type_other(self, mime_type: str) -> None:
        """Verify unrecognized MIME types return OTHER."""
        assert assets.determine_asset_type(mime_type) == AssetType.OTHER
