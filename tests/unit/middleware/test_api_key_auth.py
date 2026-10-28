"""Test which paths skip API key authentication."""

import pytest
from litestar.middleware._utils import build_exclude_path_pattern

from vapi.middleware.api_key_auth import api_key_auth_mw


@pytest.mark.parametrize(
    ("path", "expected_bypass"),
    [
        ("/docs", True),
        ("/docs/openapi.json", True),
        ("/saq", True),
        ("/saq/queues", True),
        ("/api/v1/companies/docs", False),
        ("/api/v1/companies/schema", False),
        ("/api/v1/users/saq", False),
        ("/docsearch", False),
        ("/public/file.txt", False),
    ],
)
def test_api_key_auth_exclude_matches_only_prefixes(path: str, *, expected_bypass: bool) -> None:
    """Verify only the docs and SAQ prefixes skip API key auth, never a substring elsewhere."""
    # Given the compiled exclude pattern of the API key middleware
    pattern = build_exclude_path_pattern(exclude=api_key_auth_mw.kwargs["exclude"])

    # When the request path is matched against it
    bypassed = bool(pattern and pattern.findall(path))

    # Then only the anchored prefixes bypass authentication
    assert bypassed is expected_bypass
