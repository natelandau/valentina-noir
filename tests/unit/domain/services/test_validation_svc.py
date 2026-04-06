"""Unit tests for validation services."""

from collections.abc import Callable
from uuid import uuid4

import pytest

from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.domain.services import GetModelByIdValidationService
from vapi.lib.exceptions import ValidationError

pytestmark = pytest.mark.anyio


class TestValidationService:
    """Test the validation service."""

    async def test_get_campaign_by_id(
        self,
        campaign_factory: Callable,
        company_factory: Callable,
        user_factory: Callable,
    ) -> None:
        """Verify get_campaign_by_id returns a Tortoise Campaign."""
        # Given a Tortoise campaign exists
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company, user=user)

        # When we get the campaign by id
        service = GetModelByIdValidationService()
        result = await service.get_campaign_by_id(campaign.id)

        # Then the campaign is returned
        assert str(result.id) == str(campaign.id)

    async def test_get_campaign_by_id_not_found(self) -> None:
        """Verify get_campaign_by_id raises ValidationError for missing record."""
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Campaign.*not found"):
            await service.get_campaign_by_id(uuid4())

    async def test_get_campaign_by_id_archived(
        self,
        campaign_factory: Callable,
        company_factory: Callable,
        user_factory: Callable,
    ) -> None:
        """Verify get_campaign_by_id raises ValidationError for archived record."""
        # Given an archived Tortoise campaign
        company = await company_factory()
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company, user=user, is_archived=True)

        # When/Then a ValidationError is raised
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Campaign.*not found"):
            await service.get_campaign_by_id(campaign.id)

    async def test_get_character_by_id(
        self,
        character_factory: Callable,
    ) -> None:
        """Verify get_character_by_id returns a Tortoise Character."""
        # Given a Tortoise character exists
        character = await character_factory()

        # When we get the character by id
        service = GetModelByIdValidationService()
        result = await service.get_character_by_id(character.id)

        # Then the character is returned
        assert str(result.id) == str(character.id)

    async def test_get_character_by_id_not_found(self) -> None:
        """Verify get_character_by_id raises ValidationError for missing record."""
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Character.*not found"):
            await service.get_character_by_id(uuid4())

    async def test_get_character_by_id_archived(
        self,
        character_factory: Callable,
    ) -> None:
        """Verify get_character_by_id raises ValidationError for archived record."""
        # Given an archived Tortoise character
        character = await character_factory(is_archived=True)

        # When/Then a ValidationError is raised
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Character.*not found"):
            await service.get_character_by_id(character.id)

    async def test_get_concept_by_id(self) -> None:
        """Verify get_concept_by_id returns a Tortoise CharacterConcept."""
        # Given a Tortoise concept exists (seed data)
        concept = await CharacterConcept.filter(is_archived=False).first()

        # When we get the concept by id
        service = GetModelByIdValidationService()
        result = await service.get_concept_by_id(concept.id)

        # Then the concept is returned
        assert str(result.id) == str(concept.id)

    async def test_get_concept_by_id_not_found(self) -> None:
        """Verify get_concept_by_id raises ValidationError for missing record."""
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Concept.*not found"):
            await service.get_concept_by_id(uuid4())

    async def test_get_vampire_clan_by_id(self) -> None:
        """Verify get_vampire_clan_by_id returns a Tortoise VampireClan."""
        # Given a Tortoise vampire clan exists (seed data)
        clan = await VampireClan.filter(is_archived=False).first()

        # When we get the vampire clan by id
        service = GetModelByIdValidationService()
        result = await service.get_vampire_clan_by_id(clan.id)

        # Then the vampire clan is returned
        assert str(result.id) == str(clan.id)

    async def test_get_vampire_clan_by_id_not_found(self) -> None:
        """Verify get_vampire_clan_by_id raises ValidationError for missing record."""
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Vampire clan.*not found"):
            await service.get_vampire_clan_by_id(uuid4())

    async def test_get_werewolf_auspice_by_id(self) -> None:
        """Verify get_werewolf_auspice_by_id returns a Tortoise WerewolfAuspice."""
        # Given a Tortoise werewolf auspice exists (seed data)
        auspice = await WerewolfAuspice.filter(is_archived=False).first()

        # When we get the werewolf auspice by id
        service = GetModelByIdValidationService()
        result = await service.get_werewolf_auspice_by_id(auspice.id)

        # Then the werewolf auspice is returned
        assert str(result.id) == str(auspice.id)

    async def test_get_werewolf_auspice_by_id_not_found(self) -> None:
        """Verify get_werewolf_auspice_by_id raises ValidationError for missing record."""
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Werewolf auspice.*not found"):
            await service.get_werewolf_auspice_by_id(uuid4())

    async def test_get_werewolf_tribe_by_id(self) -> None:
        """Verify get_werewolf_tribe_by_id returns a Tortoise WerewolfTribe."""
        # Given a Tortoise werewolf tribe exists (seed data)
        tribe = await WerewolfTribe.filter(is_archived=False).first()

        # When we get the werewolf tribe by id
        service = GetModelByIdValidationService()
        result = await service.get_werewolf_tribe_by_id(tribe.id)

        # Then the werewolf tribe is returned
        assert str(result.id) == str(tribe.id)

    async def test_get_werewolf_tribe_by_id_not_found(self) -> None:
        """Verify get_werewolf_tribe_by_id raises ValidationError for missing record."""
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Werewolf tribe.*not found"):
            await service.get_werewolf_tribe_by_id(uuid4())

    async def test_get_user_by_id(
        self,
        user_factory: Callable,
        company_factory: Callable,
    ) -> None:
        """Verify get_user_by_id returns a Tortoise User."""
        # Given a Tortoise user exists
        company = await company_factory()
        user = await user_factory(company=company)

        # When we get the user by id
        service = GetModelByIdValidationService()
        result = await service.get_user_by_id(user.id)

        # Then the user is returned
        assert str(result.id) == str(user.id)

    async def test_get_user_by_id_not_found(self) -> None:
        """Verify get_user_by_id raises ValidationError for missing record."""
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"User.*not found"):
            await service.get_user_by_id(uuid4())

    async def test_get_user_by_id_archived(
        self,
        user_factory: Callable,
        company_factory: Callable,
    ) -> None:
        """Verify get_user_by_id raises ValidationError for archived record."""
        # Given an archived Tortoise user
        company = await company_factory()
        user = await user_factory(company=company, is_archived=True)

        # When/Then a ValidationError is raised
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"User.*not found"):
            await service.get_user_by_id(user.id)

    async def test_get_quickroll_by_id(
        self,
        quickroll_factory: Callable[..., QuickRoll],
        company_factory: Callable,
        user_factory: Callable,
    ) -> None:
        """Verify get_quickroll_by_id returns a Tortoise QuickRoll."""
        # Given a Tortoise quick roll exists
        company = await company_factory()
        user = await user_factory(company=company)
        quickroll = await quickroll_factory(user=user)

        # When we get the quick roll by id
        service = GetModelByIdValidationService()
        result = await service.get_quickroll_by_id(quickroll.id)

        # Then the quick roll is returned
        assert str(result.id) == str(quickroll.id)

    async def test_get_quickroll_by_id_not_found(self) -> None:
        """Verify get_quickroll_by_id raises ValidationError for missing record."""
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Quick roll.*not found"):
            await service.get_quickroll_by_id(uuid4())

    async def test_get_quickroll_by_id_archived(
        self,
        quickroll_factory: Callable[..., QuickRoll],
        company_factory: Callable,
        user_factory: Callable,
    ) -> None:
        """Verify get_quickroll_by_id raises ValidationError for archived record."""
        # Given an archived Tortoise quick roll
        company = await company_factory()
        user = await user_factory(company=company)
        quickroll = await quickroll_factory(user=user, is_archived=True)

        # When/Then a ValidationError is raised
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Quick roll.*not found"):
            await service.get_quickroll_by_id(quickroll.id)
