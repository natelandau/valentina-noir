"""Unit tests for domain services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from beanie import PydanticObjectId

from vapi.constants import CharacterClass, CharacterStatus, CharacterType, GameVersion
from vapi.db.models import (
    Character,
    CharacterConcept,
    CharacterTrait,
    Trait,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)
from vapi.db.models.character import WerewolfAttributes
from vapi.domain.controllers.character.dto import CharacterTraitCreate
from vapi.domain.services import CharacterService
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable


pytestmark = pytest.mark.anyio


class TestCharacterService:
    """Test the character service."""

    async def test_update_date_killed_alive(
        self, character_factory: Callable[[dict[str, Any]], Character]
    ) -> None:
        """Test the update_date_killed method."""
        character = await character_factory()
        service = CharacterService()
        service.update_date_killed(character)
        assert character.date_killed is None

    async def test_update_date_killed_alive_to_dead(
        self, character_factory: Callable[[dict[str, Any]], Character]
    ) -> None:
        """Test the update_date_killed method."""
        character = await character_factory()
        service = CharacterService()

        # when we set the character to dead
        character.status = CharacterStatus.DEAD
        service.update_date_killed(character)

        # the date killed should be set
        assert character.date_killed is not None

    async def test_update_date_killed_dead_to_alive(
        self, character_factory: Callable[[dict[str, Any]], Character]
    ) -> None:
        """Test the update_date_killed method."""
        # Given a character that is dead
        character = await character_factory()
        service = CharacterService()
        character.status = CharacterStatus.DEAD
        service.update_date_killed(character)

        # When we set the character to alive
        character.status = CharacterStatus.ALIVE
        service.update_date_killed(character)

        # The date killed should be None
        assert character.date_killed is None

    class TestAssignVampireClanAttributes:
        """Test the assign_vampire_clan_attributes method."""

        async def test_assign_vampire_clan_attributes_no_clan(self) -> None:
            """Test the assign_vampire_clan_attributes method."""
            # Given a character that is a vampire but does not have a clan
            character = Character(
                name_first="Test",
                name_last="Character",
                character_class=CharacterClass.VAMPIRE,
                game_version=GameVersion.V5,
                type=CharacterType.PLAYER,
                user_creator_id=PydanticObjectId(),
                user_player_id=PydanticObjectId(),
                company_id=PydanticObjectId(),
                campaign_id=PydanticObjectId(),
            )
            service = CharacterService()

            # When we assign the clan attributes, A validation error should be raised
            with pytest.raises(ValidationError, match=r"Vampire clan id is required"):
                await service.assign_vampire_clan_attributes(character)

        async def test_assign_vampire_clan_attributes_clan_not_found(self) -> None:
            """Test the assign_vampire_clan_attributes method."""
            character = Character(
                name_first="Test",
                name_last="Character",
                character_class=CharacterClass.VAMPIRE,
                game_version=GameVersion.V5,
                type=CharacterType.PLAYER,
                user_creator_id=PydanticObjectId(),
                user_player_id=PydanticObjectId(),
                company_id=PydanticObjectId(),
                campaign_id=PydanticObjectId(),
            )

            service = CharacterService()

            # Given a non-existent clan
            character.vampire_attributes.clan_id = PydanticObjectId()

            # When we assign the clan attributes, A validation error should be raised
            with pytest.raises(ValidationError, match=r"Vampire clan.*not found"):
                await service.assign_vampire_clan_attributes(character)

        async def test_assign_vampire_clan_attributes_clan_found(self) -> None:
            """Test the assign_vampire_clan_attributes method."""
            character = Character(
                name_first="Test",
                name_last="Character",
                character_class=CharacterClass.VAMPIRE,
                game_version=GameVersion.V5,
                type=CharacterType.PLAYER,
                user_creator_id=PydanticObjectId(),
                user_player_id=PydanticObjectId(),
                company_id=PydanticObjectId(),
                campaign_id=PydanticObjectId(),
            )

            service = CharacterService()

            # given a clan
            clan = await VampireClan.find_one(VampireClan.is_archived == False)
            character.vampire_attributes.clan_id = clan.id

            # when we assign the clan attributes, the clan attributes should be assigned
            await service.assign_vampire_clan_attributes(character)
            assert character.vampire_attributes.clan_name == clan.name
            assert character.vampire_attributes.bane == clan.bane
            assert character.vampire_attributes.compulsion == clan.compulsion

        async def test_assign_vampire_clan_attributes_skips_non_vampire(self) -> None:
            """Verify method returns early for non-vampire characters."""
            # Given a mortal character
            character = Character(
                name_first="Test",
                name_last="Mortal",
                character_class=CharacterClass.MORTAL,
                game_version=GameVersion.V5,
                type=CharacterType.PLAYER,
                user_creator_id=PydanticObjectId(),
                user_player_id=PydanticObjectId(),
                company_id=PydanticObjectId(),
                campaign_id=PydanticObjectId(),
            )
            service = CharacterService()

            # When we call assign_vampire_clan_attributes
            # Then no error should be raised (method returns early)
            await service.assign_vampire_clan_attributes(character)

    class TestAssignWerewolfAttributes:
        """Test the assign_werewolf_attributes method."""

        async def test_assign_werewolf_attributes_no_tribe_or_auspice(self) -> None:
            """Verify ValidationError is raised when tribe and auspice IDs are missing."""
            # Given a werewolf character without tribe or auspice
            character = Character(
                name_first="Test",
                name_last="Werewolf",
                character_class=CharacterClass.WEREWOLF,
                game_version=GameVersion.V5,
                type=CharacterType.PLAYER,
                user_creator_id=PydanticObjectId(),
                user_player_id=PydanticObjectId(),
                company_id=PydanticObjectId(),
                campaign_id=PydanticObjectId(),
                werewolf_attributes=WerewolfAttributes(),
            )
            service = CharacterService()

            # When we assign werewolf attributes without then a ValidationError should be raised
            with pytest.raises(ValidationError):
                await service.assign_werewolf_attributes(character)

        async def test_assign_werewolf_attributes_tribe_not_found(self) -> None:
            """Verify ValidationError is raised when tribe is not found."""
            # Given a werewolf character with non-existent tribe
            auspice = await WerewolfAuspice.find_one(WerewolfAuspice.is_archived == False)
            character = Character(
                name_first="Test",
                name_last="Werewolf",
                character_class=CharacterClass.WEREWOLF,
                game_version=GameVersion.V5,
                type=CharacterType.PLAYER,
                user_creator_id=PydanticObjectId(),
                user_player_id=PydanticObjectId(),
                company_id=PydanticObjectId(),
                campaign_id=PydanticObjectId(),
                werewolf_attributes=WerewolfAttributes(
                    tribe_id=PydanticObjectId(), auspice_id=auspice.id
                ),
            )
            service = CharacterService()

            # When we assign werewolf attributes
            # Then a ValidationError should be raised
            with pytest.raises(ValidationError, match=r"Werewolf tribe.*not found"):
                await service.assign_werewolf_attributes(character)

        async def test_assign_werewolf_attributes_auspice_not_found(self) -> None:
            """Verify ValidationError is raised when auspice is not found."""
            # Given a werewolf character with non-existent auspice
            tribe = await WerewolfTribe.find_one(WerewolfTribe.is_archived == False)
            character = Character(
                name_first="Test",
                name_last="Werewolf",
                character_class=CharacterClass.WEREWOLF,
                game_version=GameVersion.V5,
                type=CharacterType.PLAYER,
                user_creator_id=PydanticObjectId(),
                user_player_id=PydanticObjectId(),
                company_id=PydanticObjectId(),
                campaign_id=PydanticObjectId(),
                werewolf_attributes=WerewolfAttributes(
                    tribe_id=tribe.id, auspice_id=PydanticObjectId()
                ),
            )
            service = CharacterService()

            # When we assign werewolf attributes
            # Then a ValidationError should be raised
            with pytest.raises(ValidationError, match=r"Werewolf auspice.*not found"):
                await service.assign_werewolf_attributes(character)

        async def test_assign_werewolf_attributes_success(self) -> None:
            """Verify werewolf attributes are assigned correctly when tribe and auspice exist."""
            # Given a werewolf character with valid tribe and auspice
            tribe = await WerewolfTribe.find_one(WerewolfTribe.is_archived == False)
            auspice = await WerewolfAuspice.find_one(WerewolfAuspice.is_archived == False)
            character = Character(
                name_first="Test",
                name_last="Werewolf",
                character_class=CharacterClass.WEREWOLF,
                game_version=GameVersion.V5,
                type=CharacterType.PLAYER,
                user_creator_id=PydanticObjectId(),
                user_player_id=PydanticObjectId(),
                company_id=PydanticObjectId(),
                campaign_id=PydanticObjectId(),
                werewolf_attributes=WerewolfAttributes(tribe_id=tribe.id, auspice_id=auspice.id),
            )
            service = CharacterService()

            # When we assign werewolf attributes
            await service.assign_werewolf_attributes(character)

            # Then the tribe and auspice names should be set
            assert character.werewolf_attributes.tribe_name == tribe.name
            assert character.werewolf_attributes.auspice_name == auspice.name

        async def test_assign_werewolf_attributes_skips_non_werewolf(self) -> None:
            """Verify method returns early for non-werewolf characters."""
            # Given a mortal character
            character = Character(
                name_first="Test",
                name_last="Mortal",
                character_class=CharacterClass.MORTAL,
                game_version=GameVersion.V5,
                type=CharacterType.PLAYER,
                user_creator_id=PydanticObjectId(),
                user_player_id=PydanticObjectId(),
                company_id=PydanticObjectId(),
                campaign_id=PydanticObjectId(),
            )
            service = CharacterService()

            # When we call assign_werewolf_attributes
            # Then no error should be raised (method returns early)
            await service.assign_werewolf_attributes(character)

    class TestValidateUniqueName:
        """Test the validate_unique_name method."""

        async def test_validate_unique_name_duplicate(
            self, character_factory: Callable[[dict[str, Any]], Character]
        ) -> None:
            """Verify ValidationError is raised when character name is not unique."""
            # Given an existing character
            existing_character = await character_factory(
                name_first="Duplicate", name_last="Name", character_class="MORTAL"
            )
            service = CharacterService()

            # Given a new character with the same name in the same company
            new_character = Character(
                name_first="Duplicate",
                name_last="Name",
                character_class=CharacterClass.MORTAL,
                game_version=GameVersion.V5,
                type=CharacterType.PLAYER,
                user_creator_id=PydanticObjectId(),
                user_player_id=PydanticObjectId(),
                company_id=existing_character.company_id,
                campaign_id=existing_character.campaign_id,
            )

            # When we validate the unique name
            # Then a ValidationError should be raised
            with pytest.raises(ValidationError) as exc_info:
                await service.validate_unique_name(new_character)

            # Verify the invalid_parameters contain the expected error
            assert any(
                "not unique" in p.get("message", "")
                for p in exc_info.value.extension.get("invalid_parameters", [])
            )

        async def test_validate_unique_name_different_company(
            self,
            character_factory: Callable[[dict[str, Any]], Character],
            company_factory: Callable[[dict[str, Any]], Any],
        ) -> None:
            """Verify no error when same name exists in different company."""
            # Given an existing character
            await character_factory(name_first="Same", name_last="Name", character_class="MORTAL")
            other_company = await company_factory()
            service = CharacterService()

            # Given a new character with the same name in a different company
            new_character = Character(
                name_first="Same",
                name_last="Name",
                character_class=CharacterClass.MORTAL,
                game_version=GameVersion.V5,
                type=CharacterType.PLAYER,
                user_creator_id=PydanticObjectId(),
                user_player_id=PydanticObjectId(),
                company_id=other_company.id,
                campaign_id=PydanticObjectId(),
            )

            # When we validate the unique name
            # Then no error should be raised
            await service.validate_unique_name(new_character)

        async def test_validate_unique_name_same_character(
            self, character_factory: Callable[[dict[str, Any]], Character]
        ) -> None:
            """Verify no error when validating the same character (update scenario)."""
            # Given an existing character
            character = await character_factory(
                name_first="Update", name_last="Test", character_class="MORTAL"
            )
            service = CharacterService()

            # When we validate the same character's name (simulating an update)
            # Then no error should be raised
            await service.validate_unique_name(character)

    class TestApplyConceptSpecialties:
        """Test the apply_concept_specialties method."""

        async def test_apply_concept_specialties_no_concept(
            self, character_factory: Callable[[dict[str, Any]], Character]
        ) -> None:
            """Verify method returns early when no concept_id is set."""
            # Given a character without a concept
            character = await character_factory(character_class="MORTAL")
            character.concept_id = None
            service = CharacterService()

            # When we apply concept specialties
            # Then no error should be raised
            await service.apply_concept_specialties(character)

        async def test_apply_concept_specialties_concept_not_found(
            self, character_factory: Callable[[dict[str, Any]], Character]
        ) -> None:
            """Verify ValidationError is raised when concept is not found."""
            # Given a character with a non-existent concept
            character = await character_factory(character_class="MORTAL")
            character.concept_id = PydanticObjectId()
            service = CharacterService()

            # When we apply concept specialties
            # Then a ValidationError should be raised
            with pytest.raises(ValidationError, match=r"Concept.*not found"):
                await service.apply_concept_specialties(character)

        async def test_apply_concept_specialties_success(
            self, character_factory: Callable[[dict[str, Any]], Character]
        ) -> None:
            """Verify specialties are applied from concept."""
            # Given a character with a valid concept
            concept = await CharacterConcept.find_one(CharacterConcept.is_archived == False)
            character = await character_factory(character_class="MORTAL")
            character.concept_id = concept.id
            character.specialties = []
            service = CharacterService()

            # When we apply concept specialties
            await service.apply_concept_specialties(character)

            # Then the character's specialties should match the concept's specialties
            assert character.specialties == concept.specialties

    class TestValidateClassAttributes:
        """Test the validate_class_attributes method."""

        async def test_validate_class_attributes_routes_to_vampire(
            self, character_factory: Callable[[dict[str, Any]], Character], mocker: Any
        ) -> None:
            """Verify vampire characters are routed to assign_vampire_clan_attributes."""
            # Given a vampire character
            character = await character_factory(character_class="VAMPIRE")
            service = CharacterService()

            # When we spy on assign_vampire_clan_attributes
            spy = mocker.spy(service, "assign_vampire_clan_attributes")

            # And call validate_class_attributes
            await service.validate_class_attributes(character)

            # Then assign_vampire_clan_attributes should be called
            spy.assert_called_once_with(character)

        async def test_validate_class_attributes_routes_to_werewolf(
            self, character_factory: Callable[[dict[str, Any]], Character], mocker: Any
        ) -> None:
            """Verify werewolf characters are routed to assign_werewolf_attributes."""
            # Given a werewolf character
            character = await character_factory(character_class="WEREWOLF")
            service = CharacterService()

            # When we spy on assign_werewolf_attributes
            spy = mocker.spy(service, "assign_werewolf_attributes")

            # And call validate_class_attributes
            await service.validate_class_attributes(character)

            # Then assign_werewolf_attributes should be called
            spy.assert_called_once()

        async def test_validate_class_attributes_mortal_passes(
            self, character_factory: Callable[[dict[str, Any]], Character]
        ) -> None:
            """Verify mortal characters pass validation without errors."""
            # Given a mortal character
            character = await character_factory(character_class="MORTAL")
            service = CharacterService()

            # When we validate class attributes
            # Then no error should be raised
            await service.validate_class_attributes(character)

    class TestPrepareForSave:
        """Test the prepare_for_save orchestration method."""

        async def test_prepare_for_save_calls_all_validations(
            self, character_factory: Callable[[dict[str, Any]], Character], mocker: Any
        ) -> None:
            """Verify prepare_for_save calls all validation methods."""
            # Given a valid mortal character
            character = await character_factory(character_class="MORTAL")
            service = CharacterService()

            # When we spy on the service methods
            spy_validate_unique_name = mocker.spy(service, "validate_unique_name")
            spy_update_date_killed = mocker.spy(service, "update_date_killed")
            spy_validate_class_attributes = mocker.spy(service, "validate_class_attributes")
            spy_apply_concept_specialties = mocker.spy(service, "apply_concept_specialties")

            # And call prepare_for_save
            await service.prepare_for_save(character)

            # Then all validation methods should be called
            spy_validate_unique_name.assert_called_once_with(character)
            spy_update_date_killed.assert_called_once_with(character)
            spy_validate_class_attributes.assert_called_once()
            spy_apply_concept_specialties.assert_called_once_with(character)

    class TestCharacterCreateTraitToCharacterTraits:
        """Test the character_create_trait_to_character_traits method."""

        async def test_character_create_trait_to_character_traits_success(
            self,
            character_factory: Callable[[dict[str, Any]], Character],
            debug: Callable[[Any], None],
        ) -> None:
            """Verify traits are created correctly."""
            # Given a character and trait create data
            character = await character_factory(character_class="MORTAL")
            trait1 = await Trait.find_one(Trait.is_archived == False)
            trait2 = await Trait.find_one(Trait.is_archived == False, Trait.id != trait1.id)
            trait_create_data = [
                CharacterTraitCreate(trait_id=trait1.id, value=2),
                CharacterTraitCreate(trait_id=trait2.id, value=2),
            ]

            # When we create traits for the character
            service = CharacterService()
            await service.character_create_trait_to_character_traits(character, trait_create_data)

            # Then the traits should be created correctly
            await character.sync()
            assert len(character.character_trait_ids) == len(trait_create_data)

            for character_trait in character.character_trait_ids:
                ctrait = await CharacterTrait.get(character_trait, fetch_links=True)
                assert ctrait.character_id == character.id
                assert ctrait.trait.id in [trait1.id, trait2.id]
                assert ctrait.value == 2

        async def test_character_create_trait_to_character_traits_trait_not_found(
            self,
            character_factory: Callable[[dict[str, Any]], Character],
            debug: Callable[[Any], None],
        ) -> None:
            """Verify ValidationError is raised when trait is not found."""
            # Given a character and trait create data
            character = await character_factory(character_class="MORTAL")
            trait_create_data = [CharacterTraitCreate(trait_id=PydanticObjectId(), value=2)]

            # When we create traits for the character
            # Then a ValidationError should be raised
            service = CharacterService()
            with pytest.raises(ValidationError, match=r"Trait.*not found"):
                await service.character_create_trait_to_character_traits(
                    character, trait_create_data
                )
