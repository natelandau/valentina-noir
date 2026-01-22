"""Statistics controllers."""

from __future__ import annotations

from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get

from vapi.constants import DiceSize
from vapi.db.models import Campaign, Character, Company, DiceRoll, User
from vapi.domain import deps, urls
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import docs, dto, lib


class StatisticsController(Controller):
    """Statistics controller."""

    tags = [APITags.STATISTICS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "character": Provide(deps.provide_character_by_id_and_company),
        "campaign": Provide(deps.provide_campaign_by_id),
    }
    guards = [developer_company_user_guard]

    @get(
        path=urls.Companies.STATISTICS,
        summary="Get company statistics",
        operation_id="getCompanyStatistics",
        description=docs.GET_COMPANY_STATISTICS_DESCRIPTION,
    )
    async def get_company_statistics(
        self, company: Company, num_top_traits: int = 5
    ) -> dto.RollStatistics:
        """Get company roll statistics."""
        filters = [
            DiceRoll.company_id == company.id,
            DiceRoll.is_archived == False,
            DiceRoll.dice_size == DiceSize.D10,
        ]
        return await lib.calculate_roll_statistics(filters, num_top_traits=num_top_traits)

    @get(
        path=urls.Users.STATISTICS,
        summary="Get user statistics",
        operation_id="getUserStatistics",
        description=docs.GET_USER_STATISTICS_DESCRIPTION,
    )
    async def get_user_statistics(self, user: User, num_top_traits: int = 5) -> dto.RollStatistics:
        """Get user roll statistics."""
        filters = [
            DiceRoll.user_id == user.id,
            DiceRoll.is_archived == False,
            DiceRoll.dice_size == DiceSize.D10,
        ]
        return await lib.calculate_roll_statistics(filters, num_top_traits=num_top_traits)

    @get(
        path=urls.Characters.STATISTICS,
        summary="Get character statistics",
        operation_id="getCharacterStatistics",
        description=docs.GET_CHARACTER_STATISTICS_DESCRIPTION,
    )
    async def get_character_statistics(
        self, character: Character, num_top_traits: int = 5
    ) -> dto.RollStatistics:
        """Get character roll statistics."""
        filters = [
            DiceRoll.character_id == character.id,
            DiceRoll.is_archived == False,
            DiceRoll.dice_size == DiceSize.D10,
        ]
        return await lib.calculate_roll_statistics(filters, num_top_traits=num_top_traits)

    @get(
        path=urls.Campaigns.STATISTICS,
        summary="Get campaign statistics",
        operation_id="getCampaignStatistics",
        description=docs.GET_CAMPAIGN_STATISTICS_DESCRIPTION,
    )
    async def get_campaign_statistics(
        self, campaign: Campaign, num_top_traits: int = 5
    ) -> dto.RollStatistics:
        """Get campaign roll statistics."""
        filters = [
            DiceRoll.campaign_id == campaign.id,
            DiceRoll.is_archived == False,
            DiceRoll.dice_size == DiceSize.D10,
        ]
        return await lib.calculate_roll_statistics(filters, num_top_traits=num_top_traits)
