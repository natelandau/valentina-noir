"""Test statistics."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from litestar.status_codes import HTTP_200_OK

from vapi.constants import DiceSize, RollResultType
from vapi.db.models import Campaign, Character, Company, DiceRoll, Trait, User
from vapi.db.models.diceroll import DiceRollResultSchema
from vapi.domain.urls import Characters, Companies, Users

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import Any

    from httpx import AsyncClient

pytestmark = pytest.mark.anyio


@pytest.fixture
async def create_dice_rolls(
    *,
    base_company: Company,
    base_user: User,
    base_campaign: Campaign,
    base_character: Character,
    dice_roll_factory: Callable[[dict[str, Any]], DiceRoll],
) -> Callable[..., Awaitable[tuple[Trait, Trait, Trait]]]:
    """Create dice rolls."""

    async def _inner(
        *,
        with_traits: bool = False,
        with_user: bool = False,
        with_campaign: bool = False,
        with_character: bool = False,
        **kwargs: Any,
    ) -> tuple[Trait, Trait, Trait]:
        """Create dice rolls."""
        if with_traits:
            trait1 = await Trait.find_one(Trait.is_archived == False)
            trait2 = await Trait.find_one(Trait.is_archived == False, Trait.name != trait1.name)
            trait3 = await Trait.find_one(
                Trait.is_archived == False,
                Trait.name != trait1.name,
                Trait.name != trait2.name,
            )

        await dice_roll_factory(
            company_id=base_company.id,
            user_id=base_user.id if with_user else None,
            campaign_id=base_campaign.id if with_campaign else None,
            character_id=base_character.id if with_character else None,
            trait_ids=[trait1.id, trait2.id] if with_traits else [],
            difficulty=6,
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            result=DiceRollResultSchema(
                total_result=10,
                total_result_type=RollResultType.SUCCESS,
                total_result_humanized="10",
                total_dice_roll=[1, 2, 3, 4, 5, 6],
                player_roll=[1, 2, 3, 4, 5, 6],
                desperation_roll=[],
            ),
        )

        await dice_roll_factory(
            company_id=base_company.id,
            user_id=base_user.id if with_user else None,
            campaign_id=base_campaign.id if with_campaign else None,
            character_id=base_character.id if with_character else None,
            trait_ids=[trait1.id, trait3.id] if with_traits else [],
            difficulty=10,
            num_dice=6,
            num_desperation_dice=0,
            dice_size=DiceSize.D10,
            result=DiceRollResultSchema(
                total_result=10,
                total_result_type=RollResultType.BOTCH,
                total_result_humanized="-1 Successes",
                total_dice_roll=[1, 2, 3, 4, 5, 6],
                player_roll=[1, 2, 3, 4, 5, 6],
                desperation_roll=[],
            ),
        )
        return trait1, trait2, trait3

    return _inner


class TestCompanyStatistics:
    """Test company statistics."""

    @pytest.mark.clean_db
    async def test_get_company_statistics_no_results(
        self,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        client: AsyncClient,
        debug: Callable[[Any], None],
    ) -> None:
        """Test getting company statistics."""
        response = await client.get(build_url(Companies.STATISTICS), headers=token_company_admin)
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
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
        token_company_admin: dict[str, str],
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        create_dice_rolls: Callable[..., Awaitable[tuple[Trait, Trait, Trait]]],
        debug: Callable[[Any], None],
    ) -> None:
        """Test getting company statistics."""
        # Call the fixture function to create the dice rolls
        trait1, trait2, trait3 = await create_dice_rolls(with_traits=True)

        response = await client.get(build_url(Companies.STATISTICS), headers=token_company_admin)
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
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
        base_company: Company,
        token_company_admin: dict[str, str],
        client: AsyncClient,
        create_dice_rolls: Callable[..., Awaitable[tuple[Trait, Trait, Trait]]],
        debug: Callable[[Any], None],
    ) -> None:
        """Test getting company statistics."""
        trait1, _, _ = await create_dice_rolls(base_company=base_company, with_traits=True)

        response = await client.get(
            build_url(Companies.STATISTICS, company_id=base_company.id),
            headers=token_company_admin,
            params={"num_top_traits": 1},
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
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
        token_company_admin: dict[str, str],
        client: AsyncClient,
        debug: Callable[[Any], None],
    ) -> None:
        """Test getting user statistics."""
        response = await client.get(
            build_url(Users.STATISTICS),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
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
        token_company_admin: dict[str, str],
        client: AsyncClient,
        create_dice_rolls: Callable[..., Awaitable[tuple[Trait, Trait, Trait]]],
        debug: Callable[[Any], None],
    ) -> None:
        """Test getting user statistics."""
        trait1, trait2, trait3 = await create_dice_rolls(with_traits=True, with_user=True)

        response = await client.get(
            build_url(Users.STATISTICS),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
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
        token_company_admin: dict[str, str],
        client: AsyncClient,
        create_dice_rolls: Callable[..., Awaitable[tuple[Trait, Trait, Trait]]],
        debug: Callable[[Any], None],
    ) -> None:
        """Test getting user statistics."""
        trait1, _, _ = await create_dice_rolls(with_traits=True, with_user=True)

        response = await client.get(
            build_url(Users.STATISTICS),
            headers=token_company_admin,
            params={"num_top_traits": 1},
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
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
        token_company_admin: dict[str, str],
        client: AsyncClient,
        dice_roll_factory: Callable[[dict[str, Any]], DiceRoll],
        debug: Callable[[Any], None],
    ) -> None:
        """Test getting character statistics."""
        response = await client.get(
            build_url(Characters.STATISTICS),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
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
        token_company_admin: dict[str, str],
        client: AsyncClient,
        create_dice_rolls: Callable[..., Awaitable[tuple[Trait, Trait, Trait]]],
        debug: Callable[[Any], None],
    ) -> None:
        """Test getting character statistics."""
        trait1, trait2, trait3 = await create_dice_rolls(with_traits=True, with_character=True)
        response = await client.get(
            build_url(Characters.STATISTICS),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
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
        token_company_admin: dict[str, str],
        client: AsyncClient,
        create_dice_rolls: Callable[..., Awaitable[tuple[Trait, Trait, Trait]]],
        debug: Callable[[Any], None],
    ) -> None:
        """Test getting character statistics."""
        trait1, _, _ = await create_dice_rolls(with_traits=True, with_character=True)
        response = await client.get(
            build_url(Characters.STATISTICS),
            headers=token_company_admin,
            params={"num_top_traits": 1},
        )
        assert response.status_code == HTTP_200_OK
        # debug(response.json())
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
