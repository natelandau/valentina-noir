"""Tests for avatar_url resolution on UserResponse."""

from typing import Any

import pytest

from vapi.db.sql_models.user import User
from vapi.domain.controllers.user.dto import UserResponse

pytestmark = pytest.mark.anyio


async def test_avatar_url_prefers_custom_value(company_factory: Any, user_factory: Any) -> None:
    """Verify the denormalized avatar_url column is used when set."""
    # Given a user with a custom avatar_url
    company = await company_factory()
    user = await user_factory(company=company, avatar_url="https://cdn.example/av.webp")
    loaded = await User.filter(id=user.id).prefetch_related("campaign_experiences").first()

    # When building the response
    response = UserResponse.from_model(loaded)

    # Then avatar_url is the custom value
    assert response.avatar_url == "https://cdn.example/av.webp"


async def test_avatar_url_falls_back_to_discord(company_factory: Any, user_factory: Any) -> None:
    """Verify avatar_url falls back to the Discord-derived URL when no custom avatar."""
    # Given a user with a discord profile and no custom avatar
    company = await company_factory()
    user = await user_factory(
        company=company,
        discord_profile={"id": "123", "avatar_id": "abc", "discriminator": "0001"},
    )
    loaded = await User.filter(id=user.id).prefetch_related("campaign_experiences").first()

    # When building the response
    response = UserResponse.from_model(loaded)

    # Then avatar_url is the discord-derived URL
    assert response.avatar_url is not None
    assert "discord" in response.avatar_url


async def test_avatar_url_null_when_no_avatar(company_factory: Any, user_factory: Any) -> None:
    """Verify avatar_url is None when there is neither a custom nor OAuth avatar."""
    # Given a user with no custom avatar and no OAuth profile
    company = await company_factory()
    user = await user_factory(company=company)
    loaded = await User.filter(id=user.id).prefetch_related("campaign_experiences").first()

    # When building the response
    response = UserResponse.from_model(loaded)

    # Then avatar_url is None
    assert response.avatar_url is None
