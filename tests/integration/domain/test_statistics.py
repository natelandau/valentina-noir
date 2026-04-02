"""Test statistics."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import HTTP_200_OK

from vapi.constants import DiceSize, RollResultType
from vapi.db.sql_models.character_sheet import Trait
from vapi.domain.urls import Characters, Companies, Users

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.campaign import Campaign as PgCampaign
    from vapi.db.sql_models.company import Company as PgCompany
    from vapi.db.sql_models.developer import Developer as PgDeveloper
    from vapi.db.sql_models.user import User as PgUser

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("neutralize_after_response_hook")]


@pytest.fixture
async def create_dice_rolls(
    pg_mirror_company: PgCompany,
    pg_mirror_user: PgUser,
    pg_mirror_campaign: PgCampaign,
    pg_character_factory: Callable[..., Any],
    pg_diceroll_factory: Callable[..., Any],
) -> Callable[..., Awaitable[tuple[Trait, Trait, Trait]]]:
    """Create dice rolls for statistics tests."""
    # Pre-create the character once so it's available for all calls
    character = await pg_character_factory(
        company=pg_mirror_company,
        user_player=pg_mirror_user,
        user_creator=pg_mirror_user,
        campaign=pg_mirror_campaign,
    )

    async def _inner(
        *,
        with_traits: bool = False,
        with_user: bool = False,
        with_campaign: bool = False,
        with_character: bool = False,
        **kwargs: Any,
    ) -> tuple[Trait, Trait, Trait]:
        """Create dice rolls."""
        trait1: Trait | None = None
        trait2: Trait | None = None
        trait3: Trait | None = None
        traits_for_roll1: list[Trait] = []
        traits_for_roll2: list[Trait] = []

        if with_traits:
            trait1 = await Trait.filter(is_archived=False).first()
            trait2 = await Trait.filter(is_archived=False).exclude(name=trait1.name).first()
            trait3 = (
                await Trait.filter(is_archived=False)
                .exclude(name=trait1.name)
                .exclude(name=trait2.name)
                .first()
            )
            traits_for_roll1 = [trait1, trait2]
            traits_for_roll2 = [trait1, trait3]

        company = kwargs.get("company", pg_mirror_company)

        await pg_diceroll_factory(
            company=company,
            user=pg_mirror_user if with_user else None,
            campaign=pg_mirror_campaign if with_campaign else None,
            character=character if with_character else None,
            traits=traits_for_roll1,
            difficulty=6,
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            total_result=10,
            total_result_type=RollResultType.SUCCESS,
            total_result_humanized="10",
            total_dice_roll=[1, 2, 3, 4, 5, 6],
            player_roll=[1, 2, 3, 4, 5, 6],
            desperation_roll=[],
        )

        await pg_diceroll_factory(
            company=company,
            user=pg_mirror_user if with_user else None,
            campaign=pg_mirror_campaign if with_campaign else None,
            character=character if with_character else None,
            traits=traits_for_roll2,
            difficulty=10,
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            total_result=10,
            total_result_type=RollResultType.BOTCH,
            total_result_humanized="-1 Successes",
            total_dice_roll=[1, 2, 3, 4, 5, 6],
            player_roll=[1, 2, 3, 4, 5, 6],
            desperation_roll=[],
        )
        return trait1, trait2, trait3

    return _inner


class TestCompanyStatistics:
    """Test company statistics."""

    @pytest.mark.clean_db
    async def test_get_company_statistics_no_results(
        self,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        client: AsyncClient,
        pg_mirror_company: PgCompany,
        pg_mirror_global_admin: PgDeveloper,
        pg_mirror_user: PgUser,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify company statistics returns zeros when no rolls exist."""
        response = await client.get(
            build_url(Companies.STATISTICS, company_id=pg_mirror_company.id),
            headers=token_global_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "botches": 0,
            "successes": 0,
            "failures": 0,
            "criticals": 0,
            "total_rolls": 0,
            "average_difficulty": None,
            "average_pool": None,
            "criticals_percentage": 0.0,
            "success_percentage": 0.0,
            "failure_percentage": 0.0,
            "botch_percentage": 0.0,
            "top_traits": [],
        }

    @pytest.mark.clean_db
    async def test_get_company_statistics(
        self,
        token_global_admin: dict[str, str],
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        pg_mirror_company: PgCompany,
        pg_mirror_global_admin: PgDeveloper,
        pg_mirror_user: PgUser,
        pg_mirror_campaign: PgCampaign,
        create_dice_rolls: Callable[..., Awaitable[tuple[Trait, Trait, Trait]]],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify company statistics returns correct aggregations."""
        trait1, trait2, trait3 = await create_dice_rolls(with_traits=True)

        response = await client.get(
            build_url(Companies.STATISTICS, company_id=pg_mirror_company.id),
            headers=token_global_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "botches": 1,
            "successes": 1,
            "failures": 0,
            "criticals": 0,
            "total_rolls": 2,
            "average_difficulty": 8.0,
            "average_pool": 6.0,
            "criticals_percentage": 0.0,
            "success_percentage": 50.0,
            "failure_percentage": 0.0,
            "botch_percentage": 50.0,
            "top_traits": [
                {
                    "name": trait1.name,
                    "usage_count": 2,
                    "trait_id": str(trait1.id),
                },
                {
                    "name": trait2.name,
                    "usage_count": 1,
                    "trait_id": str(trait2.id),
                },
                {
                    "name": trait3.name,
                    "usage_count": 1,
                    "trait_id": str(trait3.id),
                },
            ],
        }

    @pytest.mark.clean_db
    async def test_get_company_statistics_with_num_top_traits(
        self,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        client: AsyncClient,
        pg_mirror_company: PgCompany,
        pg_mirror_global_admin: PgDeveloper,
        pg_mirror_user: PgUser,
        pg_mirror_campaign: PgCampaign,
        create_dice_rolls: Callable[..., Awaitable[tuple[Trait, Trait, Trait]]],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify company statistics respects num_top_traits parameter."""
        trait1, _, _ = await create_dice_rolls(with_traits=True)

        response = await client.get(
            build_url(Companies.STATISTICS, company_id=pg_mirror_company.id),
            headers=token_global_admin,
            params={"num_top_traits": 1},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "botches": 1,
            "successes": 1,
            "failures": 0,
            "criticals": 0,
            "total_rolls": 2,
            "average_difficulty": 8.0,
            "average_pool": 6.0,
            "criticals_percentage": 0.0,
            "success_percentage": 50.0,
            "failure_percentage": 0.0,
            "botch_percentage": 50.0,
            "top_traits": [
                {
                    "name": trait1.name,
                    "usage_count": 2,
                    "trait_id": str(trait1.id),
                },
            ],
        }


class TestUserStatistics:
    """Test user statistics."""

    @pytest.mark.clean_db
    async def test_get_user_statistics_no_results(
        self,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        client: AsyncClient,
        pg_mirror_company: PgCompany,
        pg_mirror_global_admin: PgDeveloper,
        pg_mirror_user: PgUser,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify user statistics returns zeros when no rolls exist."""
        response = await client.get(
            build_url(
                Users.STATISTICS,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
            ),
            headers=token_global_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "botches": 0,
            "successes": 0,
            "failures": 0,
            "criticals": 0,
            "total_rolls": 0,
            "average_difficulty": None,
            "average_pool": None,
            "criticals_percentage": 0.0,
            "success_percentage": 0.0,
            "failure_percentage": 0.0,
            "botch_percentage": 0.0,
            "top_traits": [],
        }

    @pytest.mark.clean_db
    async def test_get_user_statistics(
        self,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        client: AsyncClient,
        pg_mirror_company: PgCompany,
        pg_mirror_global_admin: PgDeveloper,
        pg_mirror_user: PgUser,
        pg_mirror_campaign: PgCampaign,
        create_dice_rolls: Callable[..., Awaitable[tuple[Trait, Trait, Trait]]],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify user statistics returns correct aggregations."""
        trait1, trait2, trait3 = await create_dice_rolls(with_traits=True, with_user=True)

        response = await client.get(
            build_url(
                Users.STATISTICS,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
            ),
            headers=token_global_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "botches": 1,
            "successes": 1,
            "failures": 0,
            "criticals": 0,
            "total_rolls": 2,
            "average_difficulty": 8.0,
            "average_pool": 6.0,
            "criticals_percentage": 0.0,
            "success_percentage": 50.0,
            "failure_percentage": 0.0,
            "botch_percentage": 50.0,
            "top_traits": [
                {
                    "name": trait1.name,
                    "usage_count": 2,
                    "trait_id": str(trait1.id),
                },
                {
                    "name": trait2.name,
                    "usage_count": 1,
                    "trait_id": str(trait2.id),
                },
                {
                    "name": trait3.name,
                    "usage_count": 1,
                    "trait_id": str(trait3.id),
                },
            ],
        }

    @pytest.mark.clean_db
    async def test_get_user_statistics_with_num_top_traits(
        self,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        client: AsyncClient,
        pg_mirror_company: PgCompany,
        pg_mirror_global_admin: PgDeveloper,
        pg_mirror_user: PgUser,
        pg_mirror_campaign: PgCampaign,
        create_dice_rolls: Callable[..., Awaitable[tuple[Trait, Trait, Trait]]],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify user statistics respects num_top_traits parameter."""
        trait1, _, _ = await create_dice_rolls(with_traits=True, with_user=True)

        response = await client.get(
            build_url(
                Users.STATISTICS,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
            ),
            headers=token_global_admin,
            params={"num_top_traits": 1},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "botches": 1,
            "successes": 1,
            "failures": 0,
            "criticals": 0,
            "total_rolls": 2,
            "average_difficulty": 8.0,
            "average_pool": 6.0,
            "criticals_percentage": 0.0,
            "success_percentage": 50.0,
            "failure_percentage": 0.0,
            "botch_percentage": 50.0,
            "top_traits": [
                {
                    "name": trait1.name,
                    "usage_count": 2,
                    "trait_id": str(trait1.id),
                }
            ],
        }


class TestCharacterStatistics:
    """Test character statistics."""

    @pytest.mark.clean_db
    async def test_get_character_statistics_no_results(
        self,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        client: AsyncClient,
        pg_mirror_company: PgCompany,
        pg_mirror_global_admin: PgDeveloper,
        pg_mirror_user: PgUser,
        pg_mirror_campaign: PgCampaign,
        pg_character_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify character statistics returns zeros when no rolls exist."""
        character = await pg_character_factory(
            company=pg_mirror_company,
            user_player=pg_mirror_user,
            user_creator=pg_mirror_user,
            campaign=pg_mirror_campaign,
        )
        response = await client.get(
            build_url(
                Characters.STATISTICS,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
                character_id=character.id,
            ),
            headers=token_global_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "botches": 0,
            "successes": 0,
            "failures": 0,
            "criticals": 0,
            "total_rolls": 0,
            "average_difficulty": None,
            "average_pool": None,
            "criticals_percentage": 0.0,
            "success_percentage": 0.0,
            "failure_percentage": 0.0,
            "botch_percentage": 0.0,
            "top_traits": [],
        }

    @pytest.mark.clean_db
    async def test_get_character_statistics(
        self,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        client: AsyncClient,
        pg_mirror_company: PgCompany,
        pg_mirror_global_admin: PgDeveloper,
        pg_mirror_user: PgUser,
        pg_mirror_campaign: PgCampaign,
        create_dice_rolls: Callable[..., Awaitable[tuple[Trait, Trait, Trait]]],
        pg_character_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify character statistics returns correct aggregations."""
        trait1, trait2, trait3 = await create_dice_rolls(with_traits=True, with_character=True)

        # The create_dice_rolls fixture creates its own character internally;
        # we need to find that character to build the URL
        from vapi.db.sql_models.diceroll import DiceRoll

        dr = await DiceRoll.filter(company_id=pg_mirror_company.id).first()
        character_id = dr.character_id  # type: ignore[attr-defined]

        response = await client.get(
            build_url(
                Characters.STATISTICS,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
                character_id=character_id,
            ),
            headers=token_global_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "botches": 1,
            "successes": 1,
            "failures": 0,
            "criticals": 0,
            "total_rolls": 2,
            "average_difficulty": 8.0,
            "average_pool": 6.0,
            "criticals_percentage": 0.0,
            "success_percentage": 50.0,
            "failure_percentage": 0.0,
            "botch_percentage": 50.0,
            "top_traits": [
                {
                    "name": trait1.name,
                    "usage_count": 2,
                    "trait_id": str(trait1.id),
                },
                {
                    "name": trait2.name,
                    "usage_count": 1,
                    "trait_id": str(trait2.id),
                },
                {
                    "name": trait3.name,
                    "usage_count": 1,
                    "trait_id": str(trait3.id),
                },
            ],
        }

    @pytest.mark.clean_db
    async def test_get_character_statistics_with_num_top_traits(
        self,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        client: AsyncClient,
        pg_mirror_company: PgCompany,
        pg_mirror_global_admin: PgDeveloper,
        pg_mirror_user: PgUser,
        pg_mirror_campaign: PgCampaign,
        create_dice_rolls: Callable[..., Awaitable[tuple[Trait, Trait, Trait]]],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify character statistics respects num_top_traits parameter."""
        trait1, _, _ = await create_dice_rolls(with_traits=True, with_character=True)

        from vapi.db.sql_models.diceroll import DiceRoll

        dr = await DiceRoll.filter(company_id=pg_mirror_company.id).first()
        character_id = dr.character_id  # type: ignore[attr-defined]

        response = await client.get(
            build_url(
                Characters.STATISTICS,
                company_id=pg_mirror_company.id,
                user_id=pg_mirror_user.id,
                campaign_id=pg_mirror_campaign.id,
                character_id=character_id,
            ),
            headers=token_global_admin,
            params={"num_top_traits": 1},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "botches": 1,
            "successes": 1,
            "failures": 0,
            "criticals": 0,
            "total_rolls": 2,
            "average_difficulty": 8.0,
            "average_pool": 6.0,
            "criticals_percentage": 0.0,
            "success_percentage": 50.0,
            "failure_percentage": 0.0,
            "botch_percentage": 50.0,
            "top_traits": [
                {
                    "name": trait1.name,
                    "usage_count": 2,
                    "trait_id": str(trait1.id),
                },
            ],
        }
