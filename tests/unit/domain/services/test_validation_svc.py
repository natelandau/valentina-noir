"""Unit tests for validation services."""

from collections.abc import Callable

import pytest
from beanie import PydanticObjectId

from vapi.db.models import (
    Campaign,
    Character,
    CharacterConcept,
    CharacterTrait,
    CharSheetSection,
    Developer,
    QuickRoll,
    Trait,
    TraitCategory,
    User,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)
from vapi.domain.services import GetModelByIdValidationService
from vapi.lib.exceptions import ValidationError

pytestmark = pytest.mark.anyio


class TestValidationService:
    """Test the validation service."""

    async def test_get_campaign_by_id(
        self, campaign_factory: Callable[[dict[str, ...]], Campaign]
    ) -> None:
        """Test the get_campaign_by_id method."""
        # Given objects
        campaign = await campaign_factory()

        # When we get the campaign by id
        service = GetModelByIdValidationService()
        campaign = await service.get_campaign_by_id(campaign.id)

        # Then the campaign is returned
        assert campaign.id == campaign.id

    async def test_get_campaign_by_id_not_found(self) -> None:
        """Test the get_campaign_by_id method when the campaign is not found."""
        # When we get the campaign by non-existent id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Campaign.*not found"):
            await service.get_campaign_by_id(PydanticObjectId())

    async def test_get_campaign_by_id_archived(
        self, campaign_factory: Callable[[dict[str, ...]], Campaign]
    ) -> None:
        """Test the get_campaign_by_id method when the campaign is archived."""
        # Given objects
        campaign = await campaign_factory(is_archived=True)

        # When we get the campaign by id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Campaign.*not found"):
            await service.get_campaign_by_id(campaign.id)

    async def test_get_character_by_id(
        self, character_factory: Callable[[dict[str, ...]], Character]
    ) -> None:
        """Test the get_character_by_id method."""
        # Given objects
        character = await character_factory()

        # When we get the character by id
        service = GetModelByIdValidationService()
        character = await service.get_character_by_id(character.id)

        # Then the character is returned
        assert character.id == character.id

    async def test_get_character_by_id_not_found(self) -> None:
        """Test the get_character_by_id method when the character is not found."""
        # When we get the character by non-existent id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Character.*not found"):
            await service.get_character_by_id(PydanticObjectId())

    async def test_get_character_by_id_archived(
        self, character_factory: Callable[[dict[str, ...]], Character]
    ) -> None:
        """Test the get_character_by_id method when the character is archived."""
        # Given objects
        character = await character_factory(is_archived=True)

        # When we get the character by id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Character.*not found"):
            await service.get_character_by_id(character.id)

    async def test_get_concept_by_id(self) -> None:
        """Test the get_concept_by_id method."""
        # Given objects
        concept = await CharacterConcept.find_one(CharacterConcept.is_archived == False)

        # When we get the concept by id
        service = GetModelByIdValidationService()
        concept = await service.get_concept_by_id(concept.id)

        # Then the concept is returned
        assert concept.id == concept.id

    async def test_get_concept_by_id_not_found(self) -> None:
        """Test the get_concept_by_id method when the concept is not found."""
        # When we get the concept by non-existent id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Concept.*not found"):
            await service.get_concept_by_id(PydanticObjectId())

    async def test_get_vampire_clan_by_id(self) -> None:
        """Test the get_vampire_clan_by_id method."""
        # Given objects
        vampire_clan = await VampireClan.find_one(VampireClan.is_archived == False)

        # When we get the vampire clan by id
        service = GetModelByIdValidationService()
        vampire_clan = await service.get_vampire_clan_by_id(vampire_clan.id)

        # Then the vampire clan is returned
        assert vampire_clan.id == vampire_clan.id

    async def test_get_vampire_clan_by_id_not_found(self) -> None:
        """Test the get_vampire_clan_by_id method when the vampire clan is not found."""
        # When we get the vampire clan by non-existent id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Vampire clan.*not found"):
            await service.get_vampire_clan_by_id(PydanticObjectId())

    async def test_get_werewolf_auspice_by_id(self) -> None:
        """Test the get_werewolf_auspice_by_id method."""
        # Given objects
        werewolf_auspice = await WerewolfAuspice.find_one(WerewolfAuspice.is_archived == False)

        # When we get the werewolf auspice by id
        service = GetModelByIdValidationService()
        werewolf_auspice = await service.get_werewolf_auspice_by_id(werewolf_auspice.id)

        # Then the werewolf auspice is returned
        assert werewolf_auspice.id == werewolf_auspice.id

    async def test_get_werewolf_auspice_by_id_not_found(self) -> None:
        """Test the get_werewolf_auspice_by_id method when the werewolf auspice is not found."""
        # When we get the werewolf auspice by non-existent id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Werewolf auspice.*not found"):
            await service.get_werewolf_auspice_by_id(PydanticObjectId())

    async def test_get_werewolf_tribe_by_id(self) -> None:
        """Test the get_werewolf_tribe_by_id method."""
        # Given objects
        werewolf_tribe = await WerewolfTribe.find_one(WerewolfTribe.is_archived == False)

        # When we get the werewolf tribe by id
        service = GetModelByIdValidationService()
        werewolf_tribe = await service.get_werewolf_tribe_by_id(werewolf_tribe.id)

        # Then the werewolf tribe is returned
        assert werewolf_tribe.id == werewolf_tribe.id

    async def test_get_werewolf_tribe_by_id_not_found(self) -> None:
        """Test the get_werewolf_tribe_by_id method when the werewolf tribe is not found."""
        # When we get the werewolf tribe by non-existent id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Werewolf tribe.*not found"):
            await service.get_werewolf_tribe_by_id(PydanticObjectId())

    async def test_get_developer_by_id(
        self, developer_factory: Callable[[dict[str, ...]], Developer]
    ) -> None:
        """Test the get_developer_by_id method."""
        # Given objects
        developer = await developer_factory()

        # When we get the developer by id
        service = GetModelByIdValidationService()
        developer = await service.get_developer_by_id(developer.id)

        # Then the developer is returned
        assert developer.id == developer.id

    async def test_get_developer_by_id_not_found(self) -> None:
        """Test the get_developer_by_id method when the developer is not found."""
        # When we get the developer by non-existent id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Developer.*not found"):
            await service.get_developer_by_id(PydanticObjectId())

    async def test_get_developer_by_id_archived(
        self, developer_factory: Callable[[dict[str, ...]], Developer]
    ) -> None:
        """Test the get_developer_by_id method when the developer is archived."""
        # Given objects
        developer = await developer_factory(is_archived=True)

        # When we get the developer by id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Developer.*not found"):
            await service.get_developer_by_id(developer.id)

    async def test_get_quickroll_by_id(
        self, quickroll_factory: Callable[[dict[str, ...]], QuickRoll]
    ) -> None:
        """Test the get_quickroll_by_id method."""
        # Given objects
        quickroll = await quickroll_factory()

        # When we get the quick roll by id
        service = GetModelByIdValidationService()
        quickroll = await service.get_quickroll_by_id(quickroll.id)

        # Then the quick roll is returned
        assert quickroll.id == quickroll.id

    async def test_get_quickroll_by_id_not_found(self) -> None:
        """Test the get_quickroll_by_id method when the quick roll is not found."""
        # When we get the quick roll by non-existent id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Quick roll.*not found"):
            await service.get_quickroll_by_id(PydanticObjectId())

    async def test_get_quickroll_by_id_archived(
        self, quickroll_factory: Callable[[dict[str, ...]], QuickRoll]
    ) -> None:
        """Test the get_quickroll_by_id method when the quick roll is archived."""
        # Given objects
        quickroll = await quickroll_factory(is_archived=True)

        # When we get the quick roll by id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Quick roll.*not found"):
            await service.get_quickroll_by_id(quickroll.id)

    async def test_get_user_by_id(self, user_factory: Callable[[dict[str, ...]], User]) -> None:
        """Test the get_user_by_id method."""
        # Given objects
        user = await user_factory()

        # When we get the user by id
        service = GetModelByIdValidationService()
        user = await service.get_user_by_id(user.id)

        # Then the user is returned
        assert user.id == user.id

    async def test_get_user_by_id_not_found(self) -> None:
        """Test the get_user_by_id method when the user is not found."""
        # When we get the user by non-existent id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"User.*not found"):
            await service.get_user_by_id(PydanticObjectId())

    async def test_get_user_by_id_archived(
        self, user_factory: Callable[[dict[str, ...]], User]
    ) -> None:
        """Test the get_user_by_id method when the user is archived."""
        # Given objects
        user = await user_factory(is_archived=True)

        # When we get the user by id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"User.*not found"):
            await service.get_user_by_id(user.id)

    async def test_get_character_trait_by_id(
        self, character_trait_factory: Callable[[dict[str, ...]], CharacterTrait]
    ) -> None:
        """Test the get_character_trait_by_id method."""
        # Given objects
        character_trait = await character_trait_factory()

        # When we get the character trait by id
        service = GetModelByIdValidationService()
        character_trait = await service.get_character_trait_by_id(character_trait.id)

        # Then the character trait is returned
        assert character_trait.id == character_trait.id

    async def test_get_character_trait_by_id_not_found(self) -> None:
        """Test the get_character_trait_by_id method when the character trait is not found."""
        # When we get the character trait by non-existent id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Character trait.*not found"):
            await service.get_character_trait_by_id(PydanticObjectId())

    async def test_get_trait_by_id(self, trait_factory: Callable[[dict[str, ...]], Trait]) -> None:
        """Test the get_trait_by_id method."""
        # Given objects
        trait = await trait_factory()

        # When we get the trait by id
        service = GetModelByIdValidationService()
        trait = await service.get_trait_by_id(trait.id)

        # Then the trait is returned
        assert trait.id == trait.id

    async def test_get_trait_by_id_not_found(self) -> None:
        """Test the get_trait_by_id method when the trait is not found."""
        # When we get the trait by non-existent id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Trait.*not found"):
            await service.get_trait_by_id(PydanticObjectId())

    async def test_get_trait_by_id_archived(
        self, trait_factory: Callable[[dict[str, ...]], Trait]
    ) -> None:
        """Test the get_trait_by_id method when the trait is archived."""
        # Given objects
        trait = await trait_factory(is_archived=True)

        # When we get the trait by id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Trait.*not found"):
            await service.get_trait_by_id(trait.id)

    async def test_get_trait_category_by_id(self) -> None:
        """Test the get_trait_category_by_id method."""
        # Given objects
        trait_category = await TraitCategory.find_one(TraitCategory.is_archived == False)

        # When we get the trait category by id
        service = GetModelByIdValidationService()
        trait_category = await service.get_trait_category_by_id(trait_category.id)

        # Then the trait category is returned
        assert trait_category.id == trait_category.id

    async def test_get_trait_category_by_id_not_found(self) -> None:
        """Test the get_trait_category_by_id method when the trait category is not found."""
        # When we get the trait category by non-existent id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Trait category.*not found"):
            await service.get_trait_category_by_id(PydanticObjectId())

    async def test_get_sheet_section_by_id(self) -> None:
        """Test the get_sheet_section_by_id method."""
        # Given objects
        sheet_section = await CharSheetSection.find_one(CharSheetSection.is_archived == False)

        # When we get the sheet section by id
        service = GetModelByIdValidationService()
        sheet_section = await service.get_sheet_section_by_id(sheet_section.id)

        # Then the sheet section is returned
        assert sheet_section.id == sheet_section.id

    async def test_get_sheet_section_by_id_not_found(self) -> None:
        """Test the get_sheet_section_by_id method when the sheet section is not found."""
        # When we get the sheet section by non-existent id
        service = GetModelByIdValidationService()
        with pytest.raises(ValidationError, match=r"Sheet section.*not found"):
            await service.get_sheet_section_by_id(PydanticObjectId())
