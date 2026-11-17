"""Unit tests for character domain services."""

from datetime import date
from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from vapi.constants import CharacterStatus, CharacterType, PermissionManageNPC, UserRole
from vapi.db.sql_models.character import (
    Character,
    CharacterHealth,
    CharacterTrait,
    VampireAttributes,
    WerewolfAttributes,
)
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_sheet import Trait
from vapi.domain.controllers.character.dto import CharacterTraitCreate
from vapi.domain.controllers.character_health.dto import HealthStateSet
from vapi.domain.controllers.character_trait.dto import TrackerStateSet
from vapi.domain.services import CharacterService, TrackerService
from vapi.lib.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


class TestApplyStatusChange:
    """Test the apply_status_change method."""

    async def test_alive_character_unchanged(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify date_killed stays None when character status is ALIVE."""
        # Given an alive character
        company = await company_factory()
        character = await character_factory(company=company)

        # When applying the status change
        await CharacterService().apply_status_change(character)

        # Then date_killed remains None
        assert character.date_killed is None

    async def test_death_then_revival(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify date_killed is set on death and cleared on revival."""
        # Given an alive character
        company = await company_factory()
        character = await character_factory(company=company)
        service = CharacterService()

        # When the character dies
        character.status = CharacterStatus.DEAD
        await service.apply_status_change(character)

        # Then date_killed is set
        assert character.date_killed is not None

        # When the character is revived
        character.status = CharacterStatus.ALIVE
        await service.apply_status_change(character)

        # Then date_killed is cleared
        assert character.date_killed is None

    @pytest.mark.parametrize(
        ("status", "already_dead", "date_of_birth", "in_game_date", "expected"),
        [
            (CharacterStatus.DEAD, False, date(1960, 3, 15), date(1986, 6, 1), 26),
            (CharacterStatus.DEAD, False, None, date(1986, 6, 1), 99),
            (CharacterStatus.DEAD, False, date(1960, 3, 15), None, 99),
            (CharacterStatus.DEAD, False, date(1960, 3, 15), date(1950, 1, 1), 99),
            (CharacterStatus.DEAD, True, date(1960, 3, 15), date(1986, 6, 1), 99),
            (CharacterStatus.ALIVE, False, date(1960, 3, 15), date(1986, 6, 1), 99),
        ],
    )
    async def test_age_stored_on_death(
        self,
        character_factory: "Callable[..., Any]",
        campaign_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
        status: CharacterStatus,
        date_of_birth: date | None,
        in_game_date: date | None,
        expected: int,
        *,
        already_dead: bool,
    ) -> None:
        """Verify the in-game age is stored only when a character dies with both dates set."""
        # Given a character with a stored age of 99
        company = await company_factory()
        campaign = await campaign_factory(company=company, in_game_date=in_game_date)
        character = await character_factory(
            company=company, campaign=campaign, date_of_birth=date_of_birth, age=99
        )
        character.status = status
        if already_dead:
            character.date_killed = time_now()

        # When applying the status change
        await CharacterService().apply_status_change(character)

        # Then the age is the in-game age at death, or unchanged
        assert character.age == expected

    async def test_death_age_recorded_in_patch_changes(
        self,
        character_factory: "Callable[..., Any]",
        campaign_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify the age stored on death appears in the patch's audit changes."""
        from vapi.domain.controllers.character.dto import CharacterPatch

        # Given a living character with a date of birth in a dated campaign
        company = await company_factory()
        campaign = await campaign_factory(company=company, in_game_date=date(1986, 6, 1))
        character = await character_factory(
            company=company, campaign=campaign, date_of_birth=date(1960, 3, 15), age=99
        )

        # When a patch kills the character
        changes = await CharacterService().save_character_patch(
            character,
            CharacterPatch(status=CharacterStatus.DEAD),
            acting_user=await character.user_player,
        )

        # Then the stored age change is recorded
        assert changes["age"] == {"old": 99, "new": 26}


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
        character.concept_id = None
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
        character.concept_id = uuid4()
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


class TestApplyConceptSpecialtiesCompanyScope:
    """Test that apply_concept_specialties only uses shared or same-company concepts."""

    async def test_other_company_concept_rejected(
        self,
        character_factory: "Callable[..., Any]",
        character_concept_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify a concept owned by another company is treated as not found."""
        # Given a character pointing at a concept owned by another company
        company = await company_factory()
        other_company = await company_factory()
        concept = await character_concept_factory(company_id=other_company.id)
        character = await character_factory(character_class="MORTAL", company=company)
        character.concept_id = concept.id

        # When we apply concept specialties
        # Then a ValidationError is raised
        with pytest.raises(ValidationError, match=r"Concept.*not found"):
            await CharacterService().apply_concept_specialties(character)


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
        spy_apply_status_change = mocker.spy(service, "apply_status_change")
        spy_validate_class_attributes = mocker.spy(service, "validate_class_attributes")
        spy_apply_concept_specialties = mocker.spy(service, "apply_concept_specialties")

        # And call prepare_for_save
        await service.prepare_for_save(character)

        # Then all validation methods should be called
        spy_validate_unique_name.assert_called_once_with(character)
        spy_apply_status_change.assert_called_once_with(character)
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
        traits = await Trait.filter(is_archived=False).exclude(name="Willpower").limit(2)
        trait1, trait2 = traits[0], traits[1]
        trait_create_data = [
            CharacterTraitCreate(trait_id=trait1.id, value=2),
            CharacterTraitCreate(trait_id=trait2.id, value=2),
        ]
        service = CharacterService()

        # When we create traits for the character
        await service.character_create_trait_to_character_traits(character, trait_create_data)

        # Then the trait rows should exist with correct values, beside the derived V5 Willpower
        created_traits = (
            await CharacterTrait.filter(character=character)
            .exclude(trait__name="Willpower")
            .prefetch_related("trait")
        )
        assert len(created_traits) == 2
        created_trait_ids = {ct.trait_id for ct in created_traits}
        assert trait1.id in created_trait_ids
        assert trait2.id in created_trait_ids
        for ct in created_traits:
            assert ct.value == 2

    @pytest.mark.parametrize("excluded", ["custom", "archived"])
    async def test_character_create_rejects_custom_and_archived_traits(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
        trait_factory: "Callable[..., Any]",
        excluded: str,
    ) -> None:
        """Verify character creation rejects custom traits and archived traits."""
        # Given a new character and a trait it may not use
        company = await company_factory()
        character = await character_factory(character_class="MORTAL", company=company)
        if excluded == "custom":
            other_character = await character_factory(company=await company_factory())
            trait = await trait_factory(
                name="Foreign Custom Trait", custom_for_character_id=other_character.id
            )
        else:
            trait = await trait_factory(name="Retired Trait", is_archived=True)
        trait_create_data = [CharacterTraitCreate(trait_id=trait.id, value=1)]

        # When creating the character's traits with it
        # Then the trait is treated as not found
        with pytest.raises(ValidationError, match=r"Trait.*not found"):
            await CharacterService().character_create_trait_to_character_traits(
                character, trait_create_data
            )

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


class TestCreateTraitsWithTrackers:
    """Test tracker state and derived Willpower when creating traits for a character."""

    async def test_create_character_ignores_v5_willpower_value(
        self,
        character_factory: "Callable[..., Any]",
    ) -> None:
        """Verify a supplied V5 Willpower value is replaced by Composure + Resolve."""
        # Given a V5 character and request data with Composure 2, Resolve 3, Willpower 9
        character = await character_factory(game_version="V5", character_class="MORTAL")
        composure = await Trait.get(name="Composure", custom_for_character_id=None)
        resolve = await Trait.get(name="Resolve", custom_for_character_id=None)
        willpower = await Trait.get(name="Willpower", custom_for_character_id=None)
        data = [
            CharacterTraitCreate(trait_id=composure.id, value=2),
            CharacterTraitCreate(trait_id=resolve.id, value=3),
            CharacterTraitCreate(trait_id=willpower.id, value=9),
        ]

        # When creating the traits
        await CharacterService().character_create_trait_to_character_traits(character, data)

        # Then Willpower is 5, and there is a single Willpower row
        rows = await CharacterTrait.filter(character_id=character.id, trait_id=willpower.id)
        assert [r.value for r in rows] == [5]

    async def test_create_trait_applies_tracker_to_v5_willpower(
        self,
        character_factory: "Callable[..., Any]",
    ) -> None:
        """Verify a tracker on V5 Willpower is applied after the value is computed."""
        # Given a V5 character with Composure 2 and Resolve 3
        character = await character_factory(game_version="V5", character_class="MORTAL")
        composure = await Trait.get(name="Composure", custom_for_character_id=None)
        resolve = await Trait.get(name="Resolve", custom_for_character_id=None)
        willpower = await Trait.get(name="Willpower", custom_for_character_id=None)
        data = [
            CharacterTraitCreate(trait_id=composure.id, value=2),
            CharacterTraitCreate(trait_id=resolve.id, value=3),
            CharacterTraitCreate(
                trait_id=willpower.id, value=0, tracker=TrackerStateSet(current=3)
            ),
        ]

        # When creating the traits
        await CharacterService().character_create_trait_to_character_traits(character, data)

        # Then the counter is stored on the computed Willpower
        row = await CharacterTrait.get(character_id=character.id, trait_id=willpower.id)
        assert (row.value, row.tracker_spent) == (5, 2)

    async def test_create_trait_applies_tracker_to_v4_willpower(
        self,
        character_factory: "Callable[..., Any]",
    ) -> None:
        """Verify a counter tracker is stored on a V4 trait."""
        # Given a V4 character
        character = await character_factory(game_version="V4", character_class="MORTAL")
        willpower = await Trait.get(name="Willpower", custom_for_character_id=None)
        data = [
            CharacterTraitCreate(trait_id=willpower.id, value=6, tracker=TrackerStateSet(current=4))
        ]

        # When creating the trait
        await CharacterService().character_create_trait_to_character_traits(character, data)

        # Then 2 points are spent
        row = await CharacterTrait.get(character_id=character.id, trait_id=willpower.id)
        assert row.tracker_spent == 2

    async def test_create_trait_tracker_rejected_without_tracker(
        self,
        character_factory: "Callable[..., Any]",
    ) -> None:
        """Verify a tracker on a trait without one is rejected before anything is saved."""
        # Given a V5 character and a trait with no V5 tracker
        character = await character_factory(game_version="V5", character_class="MORTAL")
        plain = await Trait.filter(
            tracker_type_v5__isnull=True, custom_for_character_id=None, is_archived=False
        ).first()
        composure = await Trait.get(name="Composure", custom_for_character_id=None)
        data = [
            CharacterTraitCreate(trait_id=composure.id, value=2),
            CharacterTraitCreate(trait_id=plain.id, value=1, tracker=TrackerStateSet(current=1)),
        ]

        # When creating the traits
        # Then a ValidationError is raised and no rows exist
        with pytest.raises(ValidationError, match="no tracker"):
            await CharacterService().character_create_trait_to_character_traits(character, data)
        assert not await CharacterTrait.filter(character_id=character.id).exists()


class TestCreateWithHealth:
    """Test health state and validation applied while creating a character."""

    async def test_create_character_with_health_state(
        self,
        character_factory: "Callable[..., Any]",
    ) -> None:
        """Verify a starting health state is stored on a Stamina-sized track."""
        # Given a V5 character with Stamina 3 and no health row
        character = await character_factory(
            game_version="V5", character_class="MORTAL", health=False
        )
        stamina = await Trait.get(name="Stamina", custom_for_character_id=None)
        await CharacterService().character_create_trait_to_character_traits(
            character, [CharacterTraitCreate(trait_id=stamina.id, value=3)]
        )

        # When initializing with 3 damage
        await TrackerService().initialize_character(
            character=character, health=HealthStateSet(damage=3)
        )

        # Then the single health row is sized 6 and carries the damage
        rows = await CharacterHealth.filter(character_id=character.id)
        assert [(r.size, r.damage) for r in rows] == [(6, 3)]

    async def test_create_character_health_marks_over_size_rejected(
        self,
        character_factory: "Callable[..., Any]",
    ) -> None:
        """Verify damage over the computed size is rejected."""
        # Given a V5 character with no Stamina (size 3)
        character = await character_factory(
            game_version="V5", character_class="MORTAL", health=False
        )

        # When initializing with 4 damage
        # Then a ValidationError is raised
        with pytest.raises(ValidationError, match="at most"):
            await TrackerService().initialize_character(
                character=character, health=HealthStateSet(damage=4)
            )

    async def test_create_trait_tracker_over_size_rejected(
        self,
        character_factory: "Callable[..., Any]",
    ) -> None:
        """Verify a counter above the computed Willpower is rejected."""
        # Given a V5 character with Composure 1 and Resolve 1 (Willpower 2)
        character = await character_factory(game_version="V5", character_class="MORTAL")
        composure = await Trait.get(name="Composure", custom_for_character_id=None)
        resolve = await Trait.get(name="Resolve", custom_for_character_id=None)
        willpower = await Trait.get(name="Willpower", custom_for_character_id=None)
        data = [
            CharacterTraitCreate(trait_id=composure.id, value=1),
            CharacterTraitCreate(trait_id=resolve.id, value=1),
            CharacterTraitCreate(trait_id=willpower.id, tracker=TrackerStateSet(current=3)),
        ]

        # When creating the traits
        # Then a ValidationError is raised
        with pytest.raises(ValidationError, match="at most"):
            await CharacterService().character_create_trait_to_character_traits(character, data)

    async def test_create_duplicate_trait_ids_rejected(
        self,
        character_factory: "Callable[..., Any]",
    ) -> None:
        """Verify listing the same trait twice is rejected before anything is saved."""
        # Given a payload with Composure twice
        character = await character_factory(game_version="V5", character_class="MORTAL")
        composure = await Trait.get(name="Composure", custom_for_character_id=None)
        data = [
            CharacterTraitCreate(trait_id=composure.id, value=1),
            CharacterTraitCreate(trait_id=composure.id, value=2),
        ]

        # When creating the traits
        # Then a ValidationError is raised and no rows exist
        with pytest.raises(ValidationError, match="only once"):
            await CharacterService().character_create_trait_to_character_traits(character, data)
        assert not await CharacterTrait.filter(character_id=character.id).exists()


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

    async def test_archive_character_cascades_to_owned_data(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
        character_inventory_factory: "Callable[..., Any]",
        specialty_factory: "Callable[..., Any]",
        note_factory: "Callable[..., Any]",
    ) -> None:
        """Verify archive_character cascades to inventory, specialty, and notes under one batch."""
        # Given a character with inventory, a specialty, and a note
        company = await company_factory()
        character = await character_factory(character_class="MORTAL", company=company)
        inventory = await character_inventory_factory(character=character)
        specialty = await specialty_factory(character=character)
        note = await note_factory(company=company, character=character)
        service = CharacterService()

        # When we archive the character
        await service.archive_character(character)

        # Then the character and its owned data are archived under one batch id
        await character.refresh_from_db()
        await inventory.refresh_from_db()
        await specialty.refresh_from_db()
        await note.refresh_from_db()

        assert character.is_archived is True
        assert character.archive_batch_id is not None
        assert inventory.is_archived is True
        assert inventory.archive_batch_id == character.archive_batch_id
        assert specialty.is_archived is True
        assert specialty.archive_batch_id == character.archive_batch_id
        assert note.is_archived is True
        assert note.archive_batch_id == character.archive_batch_id


class TestAssertCanAssignNpcType:
    """Test CharacterService.assert_can_assign_npc_type."""

    async def test_player_blocked_when_storyteller_only(
        self,
        company_factory: "Callable[..., Any]",
        user_factory: "Callable[..., Any]",
    ) -> None:
        """Verify a player cannot assign the NPC type when the company restricts it."""
        # Given a STORYTELLER-only company and a player
        company = await company_factory(
            settings__permission_manage_npc=PermissionManageNPC.STORYTELLER
        )
        player = await user_factory(company=company, role="PLAYER")

        # When asserting NPC type assignment
        # Then PermissionDeniedError is raised
        with pytest.raises(PermissionDeniedError):
            CharacterService().assert_can_assign_npc_type(
                company=company, user=player, requested_type=CharacterType.NPC
            )

    async def test_player_allowed_when_unrestricted(
        self,
        company_factory: "Callable[..., Any]",
        user_factory: "Callable[..., Any]",
    ) -> None:
        """Verify a player may assign the NPC type when the company is unrestricted."""
        # Given an unrestricted company (default) and a player
        company = await company_factory()
        player = await user_factory(company=company, role="PLAYER")

        # When asserting NPC type assignment
        # Then no exception is raised
        CharacterService().assert_can_assign_npc_type(
            company=company, user=player, requested_type=CharacterType.NPC
        )

    async def test_non_npc_type_is_a_noop(
        self,
        company_factory: "Callable[..., Any]",
        user_factory: "Callable[..., Any]",
    ) -> None:
        """Verify assigning a non-NPC type is always allowed regardless of the setting."""
        # Given a STORYTELLER-only company and a player
        company = await company_factory(
            settings__permission_manage_npc=PermissionManageNPC.STORYTELLER
        )
        player = await user_factory(company=company, role="PLAYER")

        # When assigning PLAYER type
        # Then no exception is raised
        CharacterService().assert_can_assign_npc_type(
            company=company, user=player, requested_type=CharacterType.PLAYER
        )

    async def test_storyteller_always_allowed(
        self,
        company_factory: "Callable[..., Any]",
        user_factory: "Callable[..., Any]",
    ) -> None:
        """Verify a storyteller may assign NPC type even when the company restricts it."""
        # Given a STORYTELLER-only company and a storyteller
        company = await company_factory(
            settings__permission_manage_npc=PermissionManageNPC.STORYTELLER
        )
        storyteller = await user_factory(company=company, role="STORYTELLER")

        # When asserting NPC type assignment
        # Then no exception is raised
        CharacterService().assert_can_assign_npc_type(
            company=company, user=storyteller, requested_type=CharacterType.NPC
        )


class TestValidatePlayerAssignment:
    """Test CharacterService.validate_player_assignment."""

    @pytest.mark.parametrize("role", [UserRole.UNAPPROVED, UserRole.DEACTIVATED])
    async def test_inactive_player_rejected(
        self,
        company_factory: "Callable[..., Any]",
        user_factory: "Callable[..., Any]",
        role: UserRole,
    ) -> None:
        """Verify an unapproved or deactivated user cannot be assigned as a player."""
        # Given an inactive user
        company = await company_factory()
        user = await user_factory(company=company, role=role)

        # When validating the assignment
        # Then a ValidationError is raised
        with pytest.raises(ValidationError):
            await CharacterService().validate_player_assignment(
                user_player_id=user.id, company_id=company.id
            )

    @pytest.mark.parametrize("role", [UserRole.PLAYER, UserRole.STORYTELLER, UserRole.ADMIN])
    async def test_active_player_accepted(
        self,
        company_factory: "Callable[..., Any]",
        user_factory: "Callable[..., Any]",
        role: UserRole,
    ) -> None:
        """Verify an active user can be assigned as a player."""
        # Given an active user
        company = await company_factory()
        user = await user_factory(company=company, role=role)

        # When validating the assignment
        # Then no exception is raised
        await CharacterService().validate_player_assignment(
            user_player_id=user.id, company_id=company.id
        )


class TestSaveCharacterPatchStaleInstance:
    """Test that save_character_patch acts on the committed row, not the copy loaded earlier."""

    async def test_storyteller_archive_survives_player_patch(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify a player's patch on a stale copy cannot unarchive the character."""
        from vapi.domain.controllers.character.dto import CharacterPatch

        # Given a player's character loaded before a storyteller archives it
        company = await company_factory()
        stale = await character_factory(company=company)
        player = await stale.user_player
        await CharacterService().archive_character(await Character.get(id=stale.id))

        # When the player saves a name change through the stale copy
        # Then the save is rejected as not found
        with pytest.raises(NotFoundError):
            await CharacterService().save_character_patch(
                stale, CharacterPatch(name_first="Renamed"), acting_user=player
            )

        # And the archive persists
        committed = await Character.get(id=stale.id)
        assert committed.is_archived is True
        assert committed.archive_date is not None
        assert committed.archive_batch_id is not None
        assert committed.name_first != "Renamed"

    async def test_storyteller_reassignment_survives_player_patch(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
        user_factory: "Callable[..., Any]",
    ) -> None:
        """Verify a former player's patch on a stale copy cannot take the character back."""
        from vapi.domain.controllers.character.dto import CharacterPatch

        # Given a player's character loaded before a storyteller reassigns it
        company = await company_factory()
        stale = await character_factory(company=company)
        player = await stale.user_player
        other_player = await user_factory(company=company)
        await Character.filter(id=stale.id).update(user_player_id=other_player.id)

        # When the former player saves a biography change through the stale copy
        # Then the save is rejected
        with pytest.raises(PermissionDeniedError):
            await CharacterService().save_character_patch(
                stale, CharacterPatch(biography="Mine again"), acting_user=player
            )

        # And the new player keeps the character
        committed = await Character.get(id=stale.id)
        assert committed.user_player_id == other_player.id  # ty:ignore[unresolved-attribute]
        assert committed.biography != "Mine again"

    async def test_storyteller_type_change_survives_player_patch(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify a former player's patch on a stale copy cannot revert a STORYTELLER conversion."""
        from vapi.domain.controllers.character.dto import CharacterPatch

        # Given a player's character loaded before a storyteller converts it
        company = await company_factory()
        stale = await character_factory(company=company)
        player = await stale.user_player
        await Character.filter(id=stale.id).update(
            type=CharacterType.STORYTELLER, user_player_id=None
        )

        # When the former player saves a name change through the stale copy
        # Then the save is rejected
        with pytest.raises(PermissionDeniedError):
            await CharacterService().save_character_patch(
                stale, CharacterPatch(name_first="Renamed"), acting_user=player
            )

        # And the character stays a storyteller character with no player
        committed = await Character.get(id=stale.id)
        assert committed.type == CharacterType.STORYTELLER
        assert committed.user_player_id is None  # ty:ignore[unresolved-attribute]

    async def test_storyteller_patch_keeps_concurrent_reassignment(
        self,
        character_factory: "Callable[..., Any]",
        company_factory: "Callable[..., Any]",
        user_factory: "Callable[..., Any]",
    ) -> None:
        """Verify a permitted patch on a stale copy keeps columns it did not change."""
        from vapi.domain.controllers.character.dto import CharacterPatch

        # Given a character loaded before another storyteller reassigns it
        company = await company_factory()
        stale = await character_factory(company=company)
        storyteller = await user_factory(company=company, role=UserRole.STORYTELLER)
        other_player = await user_factory(company=company)
        await Character.filter(id=stale.id).update(user_player_id=other_player.id)

        # When a storyteller saves a name change through the stale copy
        changes = await CharacterService().save_character_patch(
            stale, CharacterPatch(name_first="Renamed"), acting_user=storyteller
        )

        # Then the name changes and the reassignment persists
        committed = await Character.get(id=stale.id)
        assert committed.name_first == "Renamed"
        assert committed.user_player_id == other_player.id  # ty:ignore[unresolved-attribute]
        assert "user_player_id" not in changes
