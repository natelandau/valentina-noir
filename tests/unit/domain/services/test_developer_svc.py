"""Unit tests for DeveloperService."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.db.sql_models.developer import Developer
from vapi.domain.services import DeveloperService

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


class TestGenerateApiKey:
    """Tests for DeveloperService.generate_api_key."""

    async def test_generate_api_key(self, developer_factory: Callable[..., Developer]) -> None:
        """Verify generate_api_key returns a 32-char key and persists hash fields."""
        # Given a developer with no key material
        developer = await developer_factory()

        # When generating an API key
        service = DeveloperService()
        key = await service.generate_api_key(developer)

        # Then the returned key is a 32-character string
        assert isinstance(key, str)
        assert len(key) == 32

        # And the DB record has all key fields populated
        refreshed = await Developer.get(id=str(developer.id))
        assert refreshed.hashed_api_key is not None
        assert refreshed.api_key_fingerprint is not None
        assert refreshed.key_generated is not None


class TestVerifyApiKey:
    """Tests for DeveloperService.verify_api_key."""

    async def test_verify_api_key_success(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify that the correct plaintext key passes verification."""
        # Given a developer with a generated key
        developer = await developer_factory()
        service = DeveloperService()
        key = await service.generate_api_key(developer)

        # When verifying the same key
        result = await service.verify_api_key(developer, key)

        # Then verification succeeds
        assert result is True

    async def test_verify_api_key_failure(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify that a wrong key fails verification."""
        # Given a developer with a generated key
        developer = await developer_factory()
        service = DeveloperService()
        await service.generate_api_key(developer)

        # When verifying a different key
        result = await service.verify_api_key(developer, "wrongkeyvalue0000000000000000000")

        # Then verification fails
        assert result is False

    async def test_verify_api_key_no_key(self, developer_factory: Callable[..., Developer]) -> None:
        """Verify that a developer with no stored key always returns False."""
        # Given a developer with no API key set
        developer = await developer_factory()

        # When verifying any key
        result = await DeveloperService().verify_api_key(developer, "somekey")

        # Then verification returns False without error
        assert result is False
