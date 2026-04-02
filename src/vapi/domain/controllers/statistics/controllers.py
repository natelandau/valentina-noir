"""Statistics controllers."""

from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get

from vapi.constants import DiceSize
from vapi.db.sql_models.campaign import Campaign
from vapi.db.sql_models.character import Character
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain import pg_deps, urls
from vapi.lib.pg_guards import pg_developer_company_user_guard
from vapi.openapi.tags import APITags

from . import docs, dto, lib


class StatisticsController(Controller):
    """Statistics controller."""

    tags = [APITags.STATISTICS.name]
    dependencies = {
        "company": Provide(pg_deps.provide_pg_company_by_id),
        "user": Provide(pg_deps.provide_user_by_id_and_company),
        "character": Provide(pg_deps.provide_character_by_id_and_company),
        "campaign": Provide(pg_deps.provide_campaign_by_id),
    }
    guards = [pg_developer_company_user_guard]

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
        return await lib.calculate_roll_statistics(
            {"company_id": company.id, "is_archived": False, "dice_size": DiceSize.D10},
            num_top_traits=num_top_traits,
        )

    @get(
        path=urls.Users.STATISTICS,
        summary="Get user statistics",
        operation_id="getUserStatistics",
        description=docs.GET_USER_STATISTICS_DESCRIPTION,
    )
    async def get_user_statistics(self, user: User, num_top_traits: int = 5) -> dto.RollStatistics:
        """Get user roll statistics."""
        return await lib.calculate_roll_statistics(
            {"user_id": user.id, "is_archived": False, "dice_size": DiceSize.D10},
            num_top_traits=num_top_traits,
        )

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
        return await lib.calculate_roll_statistics(
            {"character_id": character.id, "is_archived": False, "dice_size": DiceSize.D10},
            num_top_traits=num_top_traits,
        )

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
        return await lib.calculate_roll_statistics(
            {"campaign_id": campaign.id, "is_archived": False, "dice_size": DiceSize.D10},
            num_top_traits=num_top_traits,
        )
