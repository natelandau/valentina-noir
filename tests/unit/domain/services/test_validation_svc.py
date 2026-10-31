"""Unit tests for validation services."""

from collections.abc import Callable
from typing import Any
from uuid import uuid4

import pytest

from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.domain.services import GetModelByIdValidationService
from vapi.domain.services.validation_svc import validate_trait_ids_from_mixed_sources
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
        result = await service.get_campaign_by_id(campaign.id, company_id=company.id)

        # Then the campaign is returned
        assert str(result.id) == str(campaign.id)

    async def test_get_campaign_by_id_not_found(self) -> None:
        """Verify get_campaign_by_id raises ValidationError for missing record."""
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Campaign.*not found"):
            await service.get_campaign_by_id(uuid4(), company_id=uuid4())

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
            await service.get_campaign_by_id(campaign.id, company_id=company.id)

    async def test_get_character_by_id(
        self,
        character_factory: Callable,
    ) -> None:
        """Verify get_character_by_id returns a Tortoise Character."""
        # Given a Tortoise character exists
        character = await character_factory()

        # When we get the character by id
        service = GetModelByIdValidationService()
        result = await service.get_character_by_id(character.id, company_id=character.company_id)

        # Then the character is returned
        assert str(result.id) == str(character.id)

    async def test_get_character_by_id_not_found(self) -> None:
        """Verify get_character_by_id raises ValidationError for missing record."""
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Character.*not found"):
            await service.get_character_by_id(uuid4(), company_id=uuid4())

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
            await service.get_character_by_id(character.id, company_id=character.company_id)

    async def test_get_campaign_by_id_other_company(
        self,
        campaign_factory: Callable,
        company_factory: Callable,
    ) -> None:
        """Verify get_campaign_by_id rejects a campaign from another company."""
        # Given a campaign in one company
        campaign = await campaign_factory(company=await company_factory())

        # When/Then looking it up from another company raises ValidationError
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Campaign.*not found"):
            await service.get_campaign_by_id(campaign.id, company_id=(await company_factory()).id)

    async def test_get_character_by_id_other_company(
        self,
        character_factory: Callable,
        company_factory: Callable,
    ) -> None:
        """Verify get_character_by_id rejects a character from another company."""
        # Given a character in one company
        character = await character_factory()

        # When/Then looking it up from another company raises ValidationError
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Character.*not found"):
            await service.get_character_by_id(character.id, company_id=(await company_factory()).id)

    async def test_get_quickroll_by_id_other_company(
        self,
        quickroll_factory: Callable[..., QuickRoll],
        company_factory: Callable,
        user_factory: Callable,
    ) -> None:
        """Verify get_quickroll_by_id rejects a quick roll owned by another company's user."""
        # Given a quick roll owned by a user in one company
        quickroll = await quickroll_factory(
            user=await user_factory(company=await company_factory())
        )

        # When/Then looking it up from another company raises ValidationError
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Quick roll.*not found"):
            await service.get_quickroll_by_id(quickroll.id, company_id=(await company_factory()).id)

    async def test_get_concept_by_id(self, company_factory: Callable[..., Any]) -> None:
        """Verify get_concept_by_id returns a Tortoise CharacterConcept."""
        # Given a shared concept exists (seed data)
        company = await company_factory()
        concept = await CharacterConcept.filter(is_archived=False, company_id=None).first()

        # When we get the concept by id
        service = GetModelByIdValidationService()
        result = await service.get_concept_by_id(concept.id, company_id=company.id)

        # Then the concept is returned
        assert str(result.id) == str(concept.id)

    async def test_get_concept_by_id_not_found(self, company_factory: Callable[..., Any]) -> None:
        """Verify get_concept_by_id raises ValidationError for missing record."""
        # Given a company
        company = await company_factory()

        # When/Then looking up a missing concept raises ValidationError
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Concept.*not found"):
            await service.get_concept_by_id(uuid4(), company_id=company.id)

    async def test_get_concept_by_id_other_company(
        self,
        company_factory: Callable[..., Any],
        character_concept_factory: Callable[..., Any],
    ) -> None:
        """Verify get_concept_by_id rejects a concept owned by another company."""
        # Given a concept owned by another company
        company = await company_factory()
        concept = await character_concept_factory(company_id=(await company_factory()).id)

        # When/Then looking it up for the company raises ValidationError
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Concept.*not found"):
            await service.get_concept_by_id(concept.id, company_id=company.id)

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
        result = await service.get_quickroll_by_id(quickroll.id, company_id=company.id)

        # Then the quick roll is returned
        assert str(result.id) == str(quickroll.id)

    async def test_get_quickroll_by_id_not_found(self) -> None:
        """Verify get_quickroll_by_id raises ValidationError for missing record."""
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Quick roll.*not found"):
            await service.get_quickroll_by_id(uuid4(), company_id=uuid4())

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
            await service.get_quickroll_by_id(quickroll.id, company_id=company.id)


class TestValidateTraitIdsFromMixedSources:
    """Test resolving trait and character trait IDs."""

    async def test_resolves_character_trait_in_company(
        self, character_trait_factory: Callable
    ) -> None:
        """Verify a character trait ID from the company resolves to its trait ID."""
        # Given a character trait
        character_trait = await character_trait_factory()
        company_id = (await character_trait.character).company_id

        # When resolving it within the character's company
        result = await validate_trait_ids_from_mixed_sources(
            [character_trait.id], company_id=company_id
        )

        # Then the underlying trait ID is returned
        assert result == [character_trait.trait_id]

    async def test_rejects_character_trait_from_other_company(
        self, character_trait_factory: Callable, company_factory: Callable
    ) -> None:
        """Verify a character trait ID from another company is rejected."""
        # Given a character trait in one company
        character_trait = await character_trait_factory()

        # When/Then resolving it from another company raises ValidationError
        with pytest.raises(ValidationError, match="Trait not found"):
            await validate_trait_ids_from_mixed_sources(
                [character_trait.id], company_id=(await company_factory()).id
            )
