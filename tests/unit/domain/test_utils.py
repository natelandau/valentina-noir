"""Unit tests for domain utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.constants import UserRole
from vapi.db.models.user import DiscordProfile, GitHubProfile, GoogleProfile
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
                id="193148575306350592",
                username="username",
                global_name="global name",
                avatar_id="605d4417d0fa196299aa60386c895bc0",
                discriminator="0",
                email="test@example.com",
                verified=True,
            ),
            google_profile=GoogleProfile(
                id="google123",
                email="test@gmail.com",
                username="Google User",
                verified_email=True,
            ),
            github_profile=GitHubProfile(
                id="583231",
                login="octocat",
                username="The Octocat",
                email="octocat@github.com",
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
            "google_profile": {
                "username": "Updated Google User",
                "locale": "fr",
            },
            "github_profile": {
                "username": "Updated Octocat",
                "profile_url": "https://github.com/octocat",
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
        assert (
            patched_user.discord_profile.avatar_url
            == "https://cdn.discordapp.com/embed/avatars/0.png"
        )
        assert patched_user.google_profile.id == "google123"
        assert patched_user.google_profile.username == "Updated Google User"
        assert patched_user.google_profile.locale == "fr"
        assert patched_user.google_profile.email == user.google_profile.email
        assert patched_user.github_profile.id == "583231"
        assert patched_user.github_profile.username == "Updated Octocat"
        assert patched_user.github_profile.profile_url == "https://github.com/octocat"
        assert patched_user.github_profile.login == user.github_profile.login
