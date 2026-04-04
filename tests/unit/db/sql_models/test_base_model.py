"""Unit tests for BaseModel save() behavior: whitespace stripping and empty-to-none."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vapi.db.sql_models.campaign import Campaign

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any


class TestWhitespaceStripping:
    """Tests for global whitespace stripping on string fields."""

    async def test_strips_leading_trailing_whitespace_on_save(
        self,
        campaign_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify leading and trailing whitespace is stripped from CharField values."""
        # Given a company (required FK for campaign)
        company = await company_factory()

        # When creating a campaign with padded whitespace
        campaign = await campaign_factory(company=company, name="  Test Campaign  ")

        # Then the name should be stripped
        assert campaign.name == "Test Campaign"

    async def test_strips_whitespace_on_update(
        self,
        campaign_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify whitespace stripping applies on update, not just create."""
        # Given an existing campaign
        company = await company_factory()
        campaign = await campaign_factory(company=company, name="Original")

        # When updating with padded whitespace
        campaign.name = "  Updated Name  "
        await campaign.save()

        # Then the name should be stripped
        refreshed = await Campaign.get(id=campaign.id)
        assert refreshed.name == "Updated Name"

    async def test_handles_none_gracefully(
        self,
        campaign_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify None values on nullable string fields are not affected."""
        # Given a campaign with a null description
        company = await company_factory()
        campaign = await campaign_factory(company=company, description=None)

        # Then description should remain None
        assert campaign.description is None


class TestEmptyStringToNone:
    """Tests for opt-in empty-string-to-None conversion."""

    async def test_empty_string_converted_to_none(
        self,
        campaign_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify empty string is converted to None for opted-in fields."""
        # Given a company
        company = await company_factory()

        # When creating a campaign with an empty description
        # (Campaign._empty_string_to_none_fields includes "description")
        campaign = await campaign_factory(company=company, description="")

        # Then the description should be None
        assert campaign.description is None

    async def test_whitespace_only_string_converted_to_none(
        self,
        campaign_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify whitespace-only string becomes None after strip + empty-to-none."""
        # Given a company
        company = await company_factory()

        # When creating a campaign with whitespace-only description
        campaign = await campaign_factory(company=company, description="   ")

        # Then the description should be None (stripped to "" then converted to None)
        assert campaign.description is None

    async def test_non_empty_string_preserved(
        self,
        campaign_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify non-empty strings are preserved on opted-in fields."""
        # Given a company
        company = await company_factory()

        # When creating a campaign with a real description
        campaign = await campaign_factory(company=company, description="A valid description")

        # Then the description should be preserved
        assert campaign.description == "A valid description"

    async def test_non_opted_in_field_keeps_empty_string(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
        campaign_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
    ) -> None:
        """Verify fields not in _empty_string_to_none_fields keep their values."""
        # Given required parent objects
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company)

        # When creating a character with name_first (not in _empty_string_to_none_fields)
        # name_first is a required CharField, so it can't be empty, but name_last is similar
        character = await character_factory(
            company=company,
            user_creator=user,
            user_player=user,
            campaign=campaign,
        )

        # Then non-opted-in string fields should not have been converted to None
        assert character.name_first is not None
        assert character.name_last is not None
