"""Test the assets module."""

import pytest

from vapi.constants import AssetType
from vapi.utils import assets

pytestmark = pytest.mark.anyio


class TestSanitizeFilename:
    """Tests for sanitize_filename function."""

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            # Normal filenames are lowercased
            ("File.txt", "file.txt"),
            ("image.jpg", "image.jpg"),
            # Spaces and underscores become hyphens
            ("my document.pdf", "my-document.pdf"),
            ("my_document.pdf", "my-document.pdf"),
            ("multiple   spaces.txt", "multiple-spaces.txt"),
            # Unicode is transliterated to ASCII
            ("café-résumé.pdf", "cafe-resume.pdf"),
            ("naïve señor.txt", "naive-senor.txt"),
            # macOS screenshot narrow no-break space (\u202f)
            (
                "Screenshot 2026-03-15 at 5.56.20\u202fPM.png",
                "screenshot-2026-03-15-at-55620-pm.png",
            ),
            # Dangerous characters are stripped
            ('file"name.txt', "filename.txt"),
            ("file;name.txt", "filename.txt"),
            ("file<name>.txt", "filename.txt"),
            ("file&name.txt", "filename.txt"),
            ("file%name.txt", "filename.txt"),
            # Path traversal attempts - Path().name extracts final component
            ("../../../etc/passwd", "passwd"),
            ("file/../name.txt", "name.txt"),
            ("/path/to/file.txt", "file.txt"),
            # Control characters (\x00 is stripped by Path().name, \x1f matches \s → hyphen, \x7f stripped)
            ("file\x00name.txt", "filename.txt"),
            ("file\x1fname.txt", "file-name.txt"),
            ("file\x7fname.txt", "filename.txt"),
            # Empty or minimal after sanitization
            ("", "upload"),
            ("   ", "upload"),
            ("...", "upload"),
            ("..", "upload"),
            # Extension is preserved and lowercased
            ("PHOTO.JPG", "photo.jpg"),
        ],
    )
    def test_sanitize_filename_basic(self, filename: str, expected: str) -> None:
        """Verify filename sanitization normalizes to a URL-safe ASCII slug."""
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
        # max_stem(196) + "." + "pdf" = 200
        assert len(result) == 200
        assert result.endswith(".pdf")
        assert result == "a" * 196 + ".pdf"

    def test_sanitize_filename_combined_dangerous_patterns(self) -> None:
        """Verify multiple dangerous patterns are all sanitized."""
        # Given: A filename with multiple dangerous patterns
        dangerous = "../path\r\nfile;name<script>.txt"

        # When: Sanitizing the filename
        result = assets.sanitize_filename(dangerous)

        # Then: Result is ASCII-only, lowercase, no special characters
        assert result.isascii()
        assert "\r" not in result
        assert "\n" not in result
        assert ";" not in result
        assert "<" not in result
        assert ">" not in result
        assert result.endswith(".txt")


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
