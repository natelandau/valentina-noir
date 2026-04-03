"""Unit tests for character domain services."""

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from vapi.constants import CharacterStatus
from vapi.db.sql_models.character import (
    Character,
    CharacterTrait,
    VampireAttributes,
    WerewolfAttributes,
)
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_sheet import Trait
from vapi.domain.controllers.character.dto import CharacterTraitCreate
from vapi.domain.services import CharacterService
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


class TestUpdateDateKilled:
    """Test the update_date_killed method."""

    async def test_update_date_killed_alive(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify date_killed stays None when character status is ALIVE."""
        # Given an alive character
        company = await company_factory()
        character = await character_factory(company=company)
        service = CharacterService()

        # When we call update_date_killed on an alive character
        service.update_date_killed(character)

        # Then date_killed should remain None
        assert character.date_killed is None

    async def test_update_date_killed_alive_to_dead(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify date_killed is set when character transitions to DEAD."""
        # Given an alive character
        company = await company_factory()
        character = await character_factory(company=company)
        service = CharacterService()

        # When we set the character to dead
        character.status = CharacterStatus.DEAD
        service.update_date_killed(character)

        # Then date_killed should be set
        assert character.date_killed is not None

    async def test_update_date_killed_dead_to_alive(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify date_killed is cleared when character transitions back to ALIVE."""
        # Given a character that is dead
        company = await company_factory()
        character = await character_factory(company=company)
        service = CharacterService()
        character.status = CharacterStatus.DEAD
        service.update_date_killed(character)

        # When we set the character back to alive
        character.status = CharacterStatus.ALIVE
        service.update_date_killed(character)

        # Then date_killed should be None
        assert character.date_killed is None


class TestAssignVampireClanAttributes:
    """Test the assign_vampire_clan_attributes method."""

    async def test_assign_vampire_clan_attributes_no_clan(
        self,
        character_factory: "Callable[..., Any]",
        vampire_attributes_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify ValidationError is raised when vampire has no clan_id."""
        # Given a vampire character without a clan
        company = await company_factory()
        character = await character_factory(character_class="VAMPIRE", company=company)
        await vampire_attributes_factory(character=character)
        service = CharacterService()

        # When we assign clan attributes without a clan set
        # Then a ValidationError should be raised
        with pytest.raises(ValidationError, match=r"Vampire clan id is required"):
            await service.assign_vampire_clan_attributes(character)

    async def test_assign_vampire_clan_attributes_clan_not_found(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
        mocker: Any,
    ) -> None:
        """Verify ValidationError is raised when the specified clan does not exist."""
        from unittest.mock import MagicMock

        # Given a vampire character whose VampireAttributes has a non-existent clan_id
        company = await company_factory()
        character = await character_factory(character_class="VAMPIRE", company=company)

        # Return a fake attrs object with a non-existent clan_id from the DB query
        fake_attrs = MagicMock()
        fake_attrs.clan_id = uuid4()
        mock_qs = mocker.MagicMock()
        mock_qs.first = mocker.AsyncMock(return_value=fake_attrs)
        mocker.patch(
            "vapi.domain.services.character_svc.VampireAttributes.filter", return_value=mock_qs
        )

        # Patch VampireClan.filter so the clan lookup returns None
        mock_clan_qs = mocker.MagicMock()
        mock_clan_qs.first = mocker.AsyncMock(return_value=None)
        mocker.patch(
            "vapi.domain.services.character_svc.VampireClan.filter", return_value=mock_clan_qs
        )

        service = CharacterService()

        # When we assign clan attributes with a non-existent clan
        # Then a ValidationError should be raised
        with pytest.raises(ValidationError, match=r"Vampire clan.*not found"):
            await service.assign_vampire_clan_attributes(character)

    async def test_assign_vampire_clan_attributes_clan_found(
        self,
        character_factory: "Callable[..., Any]",
        vampire_attributes_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify clan bane and compulsion are copied to VampireAttributes when clan exists."""
        # Given a vampire character and a real clan
        clan = await VampireClan.filter(is_archived=False).first()
        company = await company_factory()
        character = await character_factory(character_class="VAMPIRE", company=company)
        await vampire_attributes_factory(character=character, clan=clan)
        service = CharacterService()

        # When we assign clan attributes
        await service.assign_vampire_clan_attributes(character)

        # Then the attributes should be populated from the clan
        vampire_attrs = await VampireAttributes.filter(character=character).first()
        await vampire_attrs.fetch_related("clan")
        assert vampire_attrs.clan_name == clan.name
        assert vampire_attrs.bane_name == clan.bane_name
        assert vampire_attrs.compulsion_name == clan.compulsion_name

    async def test_assign_vampire_clan_attributes_skips_non_vampire(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify method returns early for non-vampire characters."""
        # Given a mortal character
        company = await company_factory()
        character = await character_factory(character_class="MORTAL", company=company)
        service = CharacterService()

        # When we call assign_vampire_clan_attributes on a mortal
        # Then no error should be raised (method returns early)
        await service.assign_vampire_clan_attributes(character)


class TestAssignWerewolfAttributes:
    """Test the assign_werewolf_attributes method."""

    async def test_assign_werewolf_attributes_no_tribe_or_auspice(
        self,
        character_factory: "Callable[..., Any]",
        werewolf_attributes_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify ValidationError is raised when tribe and auspice IDs are missing."""
        # Given a werewolf character without tribe or auspice
        company = await company_factory()
        character = await character_factory(character_class="WEREWOLF", company=company)
        await werewolf_attributes_factory(character=character)
        service = CharacterService()

        # When we assign werewolf attributes without tribe/auspice set
        # Then a ValidationError should be raised
        with pytest.raises(ValidationError):
            await service.assign_werewolf_attributes(character)

    async def test_assign_werewolf_attributes_tribe_not_found(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
        mocker: Any,
    ) -> None:
        """Verify ValidationError is raised when tribe is not found."""
        from unittest.mock import MagicMock

        # Given a werewolf character whose WerewolfAttributes has non-existent tribe_id
        auspice = await WerewolfAuspice.filter(is_archived=False).first()
        company = await company_factory()
        character = await character_factory(character_class="WEREWOLF", company=company)

        # Return a fake attrs object with non-existent IDs from the DB query
        fake_attrs = MagicMock()
        fake_attrs.tribe_id = uuid4()
        fake_attrs.auspice_id = uuid4()
        mock_qs = mocker.MagicMock()
        mock_qs.first = mocker.AsyncMock(return_value=fake_attrs)
        mocker.patch(
            "vapi.domain.services.character_svc.WerewolfAttributes.filter",
            return_value=mock_qs,
        )

        # Patch WerewolfTribe.filter to return None (tribe not found)
        mock_tribe_qs = mocker.MagicMock()
        mock_tribe_qs.first = mocker.AsyncMock(return_value=None)
        mocker.patch(
            "vapi.domain.services.character_svc.WerewolfTribe.filter",
            return_value=mock_tribe_qs,
        )

        # Patch WerewolfAuspice.filter to return the real auspice
        mock_auspice_qs = mocker.MagicMock()
        mock_auspice_qs.first = mocker.AsyncMock(return_value=auspice)
        mocker.patch(
            "vapi.domain.services.character_svc.WerewolfAuspice.filter",
            return_value=mock_auspice_qs,
        )

        service = CharacterService()

        # When we assign werewolf attributes with a non-existent tribe
        # Then a ValidationError should be raised
        with pytest.raises(ValidationError, match=r"Werewolf tribe.*not found"):
            await service.assign_werewolf_attributes(character)

    async def test_assign_werewolf_attributes_auspice_not_found(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
        mocker: Any,
    ) -> None:
        """Verify ValidationError is raised when auspice is not found."""
        from unittest.mock import MagicMock

        # Given a werewolf character whose WerewolfAttributes has a non-existent auspice_id
        tribe = await WerewolfTribe.filter(is_archived=False).first()
        company = await company_factory()
        character = await character_factory(character_class="WEREWOLF", company=company)

        # Return a fake attrs object with non-existent IDs from the DB query
        fake_attrs = MagicMock()
        fake_attrs.tribe_id = uuid4()
        fake_attrs.auspice_id = uuid4()
        mock_qs = mocker.MagicMock()
        mock_qs.first = mocker.AsyncMock(return_value=fake_attrs)
        mocker.patch(
            "vapi.domain.services.character_svc.WerewolfAttributes.filter",
            return_value=mock_qs,
        )

        # Patch WerewolfTribe.filter to return the real tribe (tribe found)
        mock_tribe_qs = mocker.MagicMock()
        mock_tribe_qs.first = mocker.AsyncMock(return_value=tribe)
        mocker.patch(
            "vapi.domain.services.character_svc.WerewolfTribe.filter",
            return_value=mock_tribe_qs,
        )

        # Patch WerewolfAuspice.filter to return None (auspice not found)
        mock_auspice_qs = mocker.MagicMock()
        mock_auspice_qs.first = mocker.AsyncMock(return_value=None)
        mocker.patch(
            "vapi.domain.services.character_svc.WerewolfAuspice.filter",
            return_value=mock_auspice_qs,
        )

        service = CharacterService()

        # When we assign werewolf attributes with a non-existent auspice
        # Then a ValidationError should be raised
        with pytest.raises(ValidationError, match=r"Werewolf auspice.*not found"):
            await service.assign_werewolf_attributes(character)

    async def test_assign_werewolf_attributes_success(
        self,
        character_factory: "Callable[..., Any]",
        werewolf_attributes_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify tribe and auspice names are set when both exist."""
        # Given a werewolf character with valid tribe and auspice
        tribe = await WerewolfTribe.filter(is_archived=False).first()
        auspice = await WerewolfAuspice.filter(is_archived=False).first()
        company = await company_factory()
        character = await character_factory(character_class="WEREWOLF", company=company)
        await werewolf_attributes_factory(character=character, tribe=tribe, auspice=auspice)
        service = CharacterService()

        # When we assign werewolf attributes
        await service.assign_werewolf_attributes(character)

        # Then tribe and auspice names should be populated
        werewolf_attrs = await WerewolfAttributes.filter(character=character).first()
        await werewolf_attrs.fetch_related("tribe", "auspice")
        assert werewolf_attrs.tribe_name == tribe.name
        assert werewolf_attrs.auspice_name == auspice.name

    async def test_assign_werewolf_attributes_skips_non_werewolf(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify method returns early for non-werewolf characters."""
        # Given a mortal character
        company = await company_factory()
        character = await character_factory(character_class="MORTAL", company=company)
        service = CharacterService()

        # When we call assign_werewolf_attributes on a mortal
        # Then no error should be raised (method returns early)
        await service.assign_werewolf_attributes(character)


class TestValidateUniqueName:
    """Test the validate_unique_name method."""

    async def test_validate_unique_name_duplicate(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
        campaign_factory: "Callable[..., Any]",
    ) -> None:
        """Verify ValidationError is raised when character name is not unique within a company."""
        # Given an existing character
        company = await company_factory()
        campaign = await campaign_factory(company=company)
        existing = await character_factory(
            name_first="Duplicate", name_last="Name", company=company, campaign=campaign
        )
        service = CharacterService()

        # Given a new character with the same name in the same company
        new_character = await Character.create(
            name_first="Duplicate",
            name_last="Name",
            character_class="MORTAL",
            type="PLAYER",
            game_version="V5",
            user_creator_id=str(existing.user_creator_id),
            user_player_id=str(existing.user_player_id),
            company_id=str(company.id),
            campaign_id=str(campaign.id),
        )

        try:
            # When we validate the unique name
            # Then a ValidationError should be raised
            with pytest.raises(ValidationError) as exc_info:
                await service.validate_unique_name(new_character)

            # Then the error should mention "not unique"
            assert any(
                "not unique" in p.get("message", "")
                for p in exc_info.value.extension.get("invalid_parameters", [])
            )
        finally:
            await new_character.delete()

    async def test_validate_unique_name_different_company(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify no error when same name exists in a different company."""
        # Given an existing character in one company
        company_a = await company_factory()
        await character_factory(name_first="Same", name_last="Name", company=company_a)

        # Given a new character with the same name in a different company
        company_b = await company_factory()
        new_character = await character_factory(
            name_first="Same", name_last="Name", company=company_b
        )
        service = CharacterService()

        # When we validate the unique name
        # Then no error should be raised
        await service.validate_unique_name(new_character)

    async def test_validate_unique_name_same_character(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify no error when validating the same character (update scenario)."""
        # Given an existing character
        company = await company_factory()
        character = await character_factory(name_first="Update", name_last="Test", company=company)
        service = CharacterService()

        # When we validate the same character's name (simulating an update)
        # Then no error should be raised
        await service.validate_unique_name(character)


class TestApplyConceptSpecialties:
    """Test the apply_concept_specialties method."""

    async def test_apply_concept_specialties_no_concept(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify method returns early when no concept_id is set."""
        # Given a character without a concept
        company = await company_factory()
        character = await character_factory(character_class="MORTAL", company=company)
        character.concept_id = None  # type: ignore[attr-defined]
        service = CharacterService()

        # When we apply concept specialties
        # Then no error should be raised (method returns early)
        await service.apply_concept_specialties(character)

    async def test_apply_concept_specialties_concept_not_found(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify ValidationError is raised when concept is not found."""
        # Given a character with a non-existent concept_id
        company = await company_factory()
        character = await character_factory(character_class="MORTAL", company=company)
        character.concept_id = uuid4()  # type: ignore[attr-defined]
        service = CharacterService()

        # When we apply concept specialties
        # Then a ValidationError should be raised
        with pytest.raises(ValidationError, match=r"Concept.*not found"):
            await service.apply_concept_specialties(character)

    async def test_apply_concept_specialties_success(
        self,
        character_factory: "Callable[..., Any]",
        character_concept_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify specialties are synced from concept to the character's Specialty table."""
        # Given a concept with specialties and a character linked to it
        concept = await character_concept_factory(
            specialties=[
                {"name": "Investigation", "type": "ACTION", "description": "Finding clues"},
                {"name": "Intimidation", "type": "ACTION", "description": "Scaring people"},
            ]
        )
        company = await company_factory()
        character = await character_factory(
            character_class="MORTAL", company=company, concept=concept
        )
        service = CharacterService()

        # When we apply concept specialties
        await service.apply_concept_specialties(character)

        # Then the specialties should be created for the character
        specialties = await character.specialties.all()
        specialty_names = {s.name for s in specialties}
        assert "Investigation" in specialty_names
        assert "Intimidation" in specialty_names


class TestValidateClassAttributes:
    """Test the validate_class_attributes routing method."""

    async def test_validate_class_attributes_routes_to_vampire(
        self,
        character_factory: "Callable[..., Any]",
        vampire_attributes_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
        mocker: Any,
    ) -> None:
        """Verify vampire characters are routed to assign_vampire_clan_attributes."""
        # Given a vampire character with attributes
        company = await company_factory()
        character = await character_factory(character_class="VAMPIRE", company=company)
        await vampire_attributes_factory(character=character)
        service = CharacterService()

        # When we spy on assign_vampire_clan_attributes and call validate_class_attributes
        spy = mocker.spy(service, "assign_vampire_clan_attributes")

        # We expect a ValidationError because no clan is set, but we only care the method was called
        with pytest.raises(ValidationError):
            await service.validate_class_attributes(character)

        # Then assign_vampire_clan_attributes should have been called
        spy.assert_called_once_with(character)

    async def test_validate_class_attributes_routes_to_werewolf(
        self,
        character_factory: "Callable[..., Any]",
        werewolf_attributes_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
        mocker: Any,
    ) -> None:
        """Verify werewolf characters are routed to assign_werewolf_attributes."""
        # Given a werewolf character with attributes
        company = await company_factory()
        character = await character_factory(character_class="WEREWOLF", company=company)
        await werewolf_attributes_factory(character=character)
        service = CharacterService()

        # When we spy on assign_werewolf_attributes and call validate_class_attributes
        spy = mocker.spy(service, "assign_werewolf_attributes")

        # We expect a ValidationError because no tribe/auspice is set, but we only care the method was called
        with pytest.raises(ValidationError):
            await service.validate_class_attributes(character)

        # Then assign_werewolf_attributes should have been called
        spy.assert_called_once()

    async def test_validate_class_attributes_mortal_passes(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify mortal characters pass validation without errors."""
        # Given a mortal character
        company = await company_factory()
        character = await character_factory(character_class="MORTAL", company=company)
        service = CharacterService()

        # When we validate class attributes
        # Then no error should be raised
        await service.validate_class_attributes(character)


class TestPrepareForSave:
    """Test the prepare_for_save orchestration method."""

    async def test_prepare_for_save_calls_all_validations(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
        mocker: Any,
    ) -> None:
        """Verify prepare_for_save calls all validation methods."""
        # Given a valid mortal character
        company = await company_factory()
        character = await character_factory(character_class="MORTAL", company=company)
        service = CharacterService()

        # When we spy on all service methods
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
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify CharacterTrait rows are created for each TraitCreate item."""
        # Given a character and two real traits
        company = await company_factory()
        character = await character_factory(character_class="MORTAL", company=company)
        traits = await Trait.filter(is_archived=False).limit(2)
        trait1, trait2 = traits[0], traits[1]
        trait_create_data = [
            CharacterTraitCreate(trait_id=trait1.id, value=2),
            CharacterTraitCreate(trait_id=trait2.id, value=2),
        ]
        service = CharacterService()

        # When we create traits for the character
        await service.character_create_trait_to_character_traits(character, trait_create_data)

        # Then the trait rows should exist with correct values
        created_traits = await CharacterTrait.filter(character=character).prefetch_related("trait")
        assert len(created_traits) == 2
        created_trait_ids = {ct.trait_id for ct in created_traits}
        assert trait1.id in created_trait_ids
        assert trait2.id in created_trait_ids
        for ct in created_traits:
            assert ct.value == 2

    async def test_character_create_trait_to_character_traits_trait_not_found(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify ValidationError is raised when a trait_id does not exist."""
        # Given a character and a bogus trait_id
        company = await company_factory()
        character = await character_factory(character_class="MORTAL", company=company)
        trait_create_data = [CharacterTraitCreate(trait_id=uuid4(), value=2)]
        service = CharacterService()

        # When we try to create traits with an invalid trait_id
        # Then a ValidationError should be raised
        with pytest.raises(ValidationError, match=r"Trait.*not found"):
            await service.character_create_trait_to_character_traits(character, trait_create_data)


class TestArchiveCharacter:
    """Test the archive_character method."""

    async def test_archive_character(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify archive_character sets is_archived=True and populates archive_date."""
        # Given an active character
        company = await company_factory()
        character = await character_factory(character_class="MORTAL", company=company)
        assert character.is_archived is False
        assert character.archive_date is None
        service = CharacterService()

        # When we archive the character
        await service.archive_character(character)

        # Then the character should be archived with a date set
        await character.refresh_from_db()
        assert character.is_archived is True
        assert character.archive_date is not None
