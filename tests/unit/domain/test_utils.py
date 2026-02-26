"""Unit tests for domain utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.constants import UserRole
from vapi.db.models.user import DiscordProfile
from vapi.domain.utils import patch_document_from_dict

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.models import Company, User

pytestmark = pytest.mark.anyio


class TestPatchDocumentFromDict:
    """Test patch_document_from_dict function."""

    async def test_patch_document_from_dict(
        self,
        company_factory: Callable[[...], Company],
        debug: Callable[[...], None],
        user_factory: Callable[[...], User],
    ) -> None:
        """Verify patch_document_from_dict updates a document from a dictionary."""
        # Given a user
        company = await company_factory()
        user = await user_factory(
            name_first="Test",
            name_last="User",
            username="test_user",
            email="test@example.com",
            role=UserRole.PLAYER,
            company_id=company.id,
            discord_profile=DiscordProfile(
                id="discord id",
                username="username",
                global_name="global name",
                avatar_id="avatar id",
                avatar_url="avatar url",
                discriminator="discriminator",
                email="test@example.com",
                verified=True,
            ),
        )

        # Given a dictionary of data to patch the user with
        data = {
            "name_first": "updated",
            "nonexistent_key": "nonexistent value",
            "discord_profile": {
                "global_name": "updated global name",
                "avatar_id": None,
                "nonexistent_key": "nonexistent value",
            },
        }

        # When we patch the user with the dictionary
        patched_user = patch_document_from_dict(user, data)

        # Then the user is patched
        assert patched_user.name_first == "updated"
        assert patched_user.email == user.email
        assert patched_user.role == user.role
        assert patched_user.company_id == user.company_id
        assert patched_user.discord_profile.id == user.discord_profile.id
        assert patched_user.discord_profile.global_name == "updated global name"
        assert patched_user.discord_profile.avatar_id is None
        assert patched_user.discord_profile.avatar_url == user.discord_profile.avatar_url
