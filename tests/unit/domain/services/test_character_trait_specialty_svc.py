"""Test the specialty methods of the character trait service."""

from dataclasses import dataclass, replace

import pytest
from litestar.stores.memory import MemoryStore

from vapi.constants import (
    SPECIALTY_XP_COST,
    CharacterType,
    PermissionsFreeTraitChanges,
    PermissionsRecoupXP,
    TraitModifyCurrency,
    UserRole,
)
from vapi.db.sql_models.character import Character, CharacterTrait, CharacterTraitSpecialty
from vapi.db.sql_models.character_sheet import CharSheetSection, Trait
from vapi.db.sql_models.company import Company, CompanySettings
from vapi.db.sql_models.user import CampaignExperience, User
from vapi.domain.controllers.character_trait.dto import (
    CHARACTER_TRAIT_PREFETCH,
    CharacterTraitResponse,
)
from vapi.domain.services import CharacterTraitService
from vapi.lib.exceptions import NotEnoughXPError, PermissionDeniedError, ValidationError

pytestmark = pytest.mark.anyio


@dataclass
class Scenario:
    """Standard scaffold for specialty tests."""

    svc: CharacterTraitService
    company: Company
    user: User
    character: Character
    char_trait: CharacterTrait
    experience: CampaignExperience


@pytest.fixture
def make_scenario(
    company_factory,
    user_factory,
    character_factory,
    character_trait_factory,
    campaign_factory,
    campaign_experience_factory,
):
    """Return a factory building a company, player character, ability trait, and XP."""

    async def _make(
        *,
        enabled: bool = True,
        xp: int = 5,
        starting_points: int = 0,
        recoup: PermissionsRecoupXP = PermissionsRecoupXP.UNRESTRICTED,
        role: UserRole = UserRole.ADMIN,
        character_type: CharacterType = CharacterType.PLAYER,
        trait: Trait | None = None,
        value: int = 1,
        **settings: object,
    ) -> Scenario:
        company = await company_factory(
            settings__specialty_xp_cost_enabled=enabled,
            settings__permission_recoup_xp=recoup,
            **{f"settings__{k}": v for k, v in settings.items()},
        )
        user = await user_factory(company=company, role=role)
        campaign = await campaign_factory(company=company)
        if character_type == CharacterType.PLAYER:
            character = await character_factory(
                company=company,
                user_player=user,
                campaign=campaign,
                starting_points=starting_points,
            )
        else:
            character = await character_factory(
                company=company, campaign=campaign, type=character_type
            )
        experience = await campaign_experience_factory(
            user=user, campaign=campaign, xp_current=xp, xp_total=xp
        )
        if trait is None:
            trait = await Trait.filter(
                sheet_section__name="Abilities", is_archived=False, custom_for_character_id=None
            ).first()
        char_trait = await character_trait_factory(character=character, trait=trait, value=value)
        return Scenario(
            svc=CharacterTraitService(),
            company=company,
            user=user,
            character=character,
            char_trait=char_trait,
            experience=experience,
        )

    return _make


async def _add(
    s: Scenario, name: str = "Sniping", currency: TraitModifyCurrency = TraitModifyCurrency.XP
) -> CharacterTrait:
    return await s.svc.add_specialty(
        company=s.company,
        user=s.user,
        character=s.character,
        character_trait=s.char_trait,
        name=name,
        currency=currency,
    )


async def _xp(s: Scenario) -> int:
    await s.experience.refresh_from_db()
    return s.experience.xp_current


class TestAddSpecialty:
    """Test add_specialty."""

    async def test_add_free_when_setting_off(self, make_scenario) -> None:
        """Verify no charge when the setting is off."""
        # Given the setting off
        s = await make_scenario(enabled=False)

        # When adding with XP currency
        result = await _add(s)

        # Then it is free
        spec = result.specialties[0]
        assert spec.cost_paid == 0
        assert spec.currency_paid == TraitModifyCurrency.NO_COST
        assert await _xp(s) == 5

    async def test_add_setting_off_skips_free_trait_permission(self, make_scenario) -> None:
        """Verify the free-trait permission is not checked when the setting is off."""
        # Given the setting off, storyteller-only free changes, and a player user
        s = await make_scenario(
            enabled=False,
            role=UserRole.PLAYER,
            permission_free_trait_changes=PermissionsFreeTraitChanges.STORYTELLER,
        )

        # When adding at NO_COST
        result = await _add(s, currency=TraitModifyCurrency.NO_COST)

        # Then it succeeds at no cost
        assert result.specialties[0].cost_paid == 0

    async def test_add_spends_xp_when_setting_on(self, make_scenario) -> None:
        """Verify XP is spent when the setting is on."""
        # Given the setting on and 5 XP
        s = await make_scenario(xp=5)

        # When adding with XP
        result = await _add(s)

        # Then 3 XP is spent
        spec = result.specialties[0]
        assert await _xp(s) == 5 - SPECIALTY_XP_COST
        assert spec.cost_paid == SPECIALTY_XP_COST
        assert spec.currency_paid == TraitModifyCurrency.XP

    async def test_add_rejects_insufficient_xp(self, make_scenario) -> None:
        """Verify NotEnoughXPError and no row when XP is short."""
        # Given 2 XP
        s = await make_scenario(xp=2)

        # When adding with XP
        # Then it raises and nothing is created
        with pytest.raises(NotEnoughXPError):
            await _add(s)
        assert await CharacterTraitSpecialty.filter(character_trait_id=s.char_trait.id).count() == 0

    async def test_add_spends_starting_points_when_setting_on(self, make_scenario) -> None:
        """Verify starting points are deducted."""
        # Given 4 starting points
        s = await make_scenario(starting_points=4)

        # When adding with starting points
        result = await _add(s, currency=TraitModifyCurrency.STARTING_POINTS)

        # Then 1 is left and the payment is recorded
        await s.character.refresh_from_db()
        assert s.character.starting_points == 1
        assert result.specialties[0].currency_paid == TraitModifyCurrency.STARTING_POINTS

    async def test_add_rejects_insufficient_starting_points(self, make_scenario) -> None:
        """Verify ValidationError when starting points are short."""
        # Given 2 starting points
        s = await make_scenario(starting_points=2)

        # When adding with starting points
        # Then it raises, leaves the points alone, and creates nothing
        with pytest.raises(ValidationError, match="starting points"):
            await _add(s, currency=TraitModifyCurrency.STARTING_POINTS)
        await s.character.refresh_from_db()
        assert s.character.starting_points == 2
        assert await CharacterTraitSpecialty.filter(character_trait_id=s.char_trait.id).count() == 0

    async def test_add_no_cost_respects_free_trait_permission(self, make_scenario) -> None:
        """Verify NO_COST honors permission_free_trait_changes for players."""
        # Given storyteller-only free changes and a player acting on their own character
        s = await make_scenario(
            role=UserRole.PLAYER,
            permission_free_trait_changes=PermissionsFreeTraitChanges.STORYTELLER,
        )

        # When adding at NO_COST
        # Then it is denied
        with pytest.raises(PermissionDeniedError):
            await _add(s, currency=TraitModifyCurrency.NO_COST)

    async def test_add_npc_rejects_xp_when_setting_on(self, make_scenario) -> None:
        """Verify NPCs cannot pay with XP."""
        # Given an NPC character
        s = await make_scenario(character_type=CharacterType.NPC)

        # When adding with XP
        # Then it raises
        with pytest.raises(ValidationError):
            await _add(s)

    async def test_add_rejects_non_ability(self, make_scenario) -> None:
        """Verify non-ability traits are rejected."""
        # Given an Attributes trait
        trait = await Trait.filter(
            sheet_section__name="Attributes", is_archived=False, custom_for_character_id=None
        ).first()
        s = await make_scenario(trait=trait)

        # When adding
        # Then it raises
        with pytest.raises(ValidationError, match="ability"):
            await _add(s)

    async def test_add_rejects_zero_value(self, make_scenario) -> None:
        """Verify an ability at 0 is rejected."""
        # Given an ability at value 0
        s = await make_scenario(value=0)

        # When adding
        # Then it raises
        with pytest.raises(ValidationError, match="dot"):
            await _add(s)

    async def test_add_rejects_duplicate_name_case_insensitive(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify duplicates are rejected regardless of case and whitespace."""
        # Given an existing specialty
        s = await make_scenario()
        await character_trait_specialty_factory(character_trait=s.char_trait, name="Sniping")

        # When adding a case-variant
        # Then it raises
        with pytest.raises(ValidationError, match="already exists"):
            await _add(s, name="  sniping ")

    async def test_add_rejects_short_name(self, make_scenario) -> None:
        """Verify names under 3 characters are rejected."""
        # Given a scenario
        s = await make_scenario()

        # When adding "ab"
        # Then it raises
        with pytest.raises(ValidationError, match="3 to 50"):
            await _add(s, name="ab")

    async def test_add_allows_custom_ability(
        self, make_scenario, trait_factory, character_trait_factory
    ) -> None:
        """Verify custom abilities accept specialties."""
        # Given a character with a custom trait of its own in the Abilities section
        section = await CharSheetSection.filter(name="Abilities").first()
        base = await make_scenario()
        trait = await trait_factory(
            custom_for_character=base.character,
            sheet_section=section,
            category_id=(await Trait.get(id=base.char_trait.trait_id)).category_id,
        )
        custom_char_trait = await character_trait_factory(
            character=base.character, trait=trait, value=1
        )
        s = replace(base, char_trait=custom_char_trait)

        # When adding
        result = await _add(s)

        # Then it is created on the custom trait
        assert result.id == custom_char_trait.id
        assert [sp.name for sp in result.specialties] == ["Sniping"]

    async def test_add_starting_points_uses_stored_balance(self, make_scenario) -> None:
        """Verify a spend from a stale character deducts from the stored balance."""
        # Given a character read at 10 points while 5 are stored
        s = await make_scenario(starting_points=10)
        await Character.filter(id=s.character.id).update(starting_points=5)

        # When adding with starting points
        await _add(s, currency=TraitModifyCurrency.STARTING_POINTS)

        # Then the stored balance pays and the instance matches it
        assert (await Character.get(id=s.character.id)).starting_points == 5 - SPECIALTY_XP_COST
        assert s.character.starting_points == 5 - SPECIALTY_XP_COST

    async def test_add_starting_points_rejects_when_stored_balance_short(
        self, make_scenario
    ) -> None:
        """Verify a stale character showing enough points cannot overdraw the stored balance."""
        # Given a character read at 10 points while 1 is stored
        s = await make_scenario(starting_points=10)
        await Character.filter(id=s.character.id).update(starting_points=1)

        # When adding with starting points
        # Then it is refused, the balance is untouched, and nothing is created
        with pytest.raises(ValidationError, match="starting points"):
            await _add(s, currency=TraitModifyCurrency.STARTING_POINTS)
        assert (await Character.get(id=s.character.id)).starting_points == 1
        assert await CharacterTraitSpecialty.filter(character_trait_id=s.char_trait.id).count() == 0


class TestRenameSpecialty:
    """Test rename_specialty."""

    async def test_rename_updates_name_without_cost(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify rename changes only the name."""
        # Given a paid specialty
        s = await make_scenario()
        spec = await character_trait_specialty_factory(
            character_trait=s.char_trait,
            name="Sniping",
            cost_paid=3,
            currency_paid=TraitModifyCurrency.XP,
        )

        # When renaming
        result = await s.svc.rename_specialty(
            user=s.user,
            character=s.character,
            character_trait=s.char_trait,
            specialty=spec,
            name="Archery",
        )

        # Then the name changes and XP is untouched
        assert result.specialties[0].name == "Archery"
        assert await _xp(s) == 5

    async def test_rename_rejects_duplicate(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify duplicates are rejected, but a case-only self rename is allowed."""
        # Given two specialties
        s = await make_scenario()
        first = await character_trait_specialty_factory(
            character_trait=s.char_trait, name="Sniping"
        )
        await character_trait_specialty_factory(character_trait=s.char_trait, name="Archery")

        # When renaming first to the other's name with different case
        # Then it raises
        with pytest.raises(ValidationError, match="already exists"):
            await s.svc.rename_specialty(
                user=s.user,
                character=s.character,
                character_trait=s.char_trait,
                specialty=first,
                name="ARCHERY",
            )

        # And renaming to its own name in a different case succeeds
        result = await s.svc.rename_specialty(
            user=s.user,
            character=s.character,
            character_trait=s.char_trait,
            specialty=first,
            name="SNIPING",
        )
        assert "SNIPING" in {sp.name for sp in result.specialties}


class TestRemoveSpecialty:
    """Test remove_specialty."""

    async def _remove(self, s: Scenario, spec: CharacterTraitSpecialty) -> None:
        await s.svc.remove_specialty(
            company=s.company, user=s.user, character=s.character, specialty=spec
        )

    async def _paid(
        self,
        factory,
        s: Scenario,
        currency: TraitModifyCurrency = TraitModifyCurrency.XP,
        cost: int = 3,
    ) -> CharacterTraitSpecialty:
        return await factory(
            character_trait=s.char_trait, name="Sniping", cost_paid=cost, currency_paid=currency
        )

    @pytest.mark.parametrize(
        "recoup", [PermissionsRecoupXP.UNRESTRICTED, PermissionsRecoupXP.WITHIN_SESSION]
    )
    async def test_remove_refunds_xp_when_recoup_allows(
        self, make_scenario, character_trait_specialty_factory, recoup
    ) -> None:
        """Verify XP is refunded for UNRESTRICTED and WITHIN_SESSION."""
        # Given a paid specialty
        s = await make_scenario(recoup=recoup)
        spec = await self._paid(character_trait_specialty_factory, s)

        # When removed
        await self._remove(s, spec)

        # Then 3 XP returns and the row is gone
        assert await _xp(s) == 8
        assert not await CharacterTraitSpecialty.filter(id=spec.id).exists()

    async def test_remove_no_refund_when_recoup_denied(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify DENIED removes without refunding XP."""
        # Given DENIED and a paid specialty
        s = await make_scenario(recoup=PermissionsRecoupXP.DENIED)
        spec = await self._paid(character_trait_specialty_factory, s)

        # When removed
        await self._remove(s, spec)

        # Then no refund
        assert await _xp(s) == 5
        assert not await CharacterTraitSpecialty.filter(id=spec.id).exists()

    async def test_remove_refunds_starting_points_when_recoup_denied(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify starting points are refunded even under DENIED."""
        # Given DENIED and a specialty paid with starting points
        s = await make_scenario(recoup=PermissionsRecoupXP.DENIED, starting_points=1)
        spec = await self._paid(
            character_trait_specialty_factory, s, TraitModifyCurrency.STARTING_POINTS
        )

        # When removed
        await self._remove(s, spec)

        # Then 3 points return
        await s.character.refresh_from_db()
        assert s.character.starting_points == 4

    async def test_remove_refunds_after_setting_turned_off(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify a paid specialty still refunds after the cost setting is disabled."""
        # Given a specialty paid while the setting was on
        s = await make_scenario()
        spec = await self._paid(character_trait_specialty_factory, s)

        # When the setting is turned off and it is removed
        await CompanySettings.filter(company_id=s.company.id).update(
            specialty_xp_cost_enabled=False
        )
        await s.company.fetch_related("settings")
        await self._remove(s, spec)

        # Then it is refunded
        assert await _xp(s) == 8

    async def test_remove_free_specialty_never_refunds(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify a free specialty gives nothing back after the setting is enabled."""
        # Given a free specialty and the setting now on
        s = await make_scenario(enabled=True)
        spec = await character_trait_specialty_factory(character_trait=s.char_trait, name="Sniping")

        # When removed
        await self._remove(s, spec)

        # Then XP is unchanged
        assert await _xp(s) == 5

    async def test_remove_already_deleted_specialty_refunds_nothing(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify a second removal of the same specialty does not refund it again."""
        # Given a paid specialty and a stale copy of it, as two racing requests would hold
        s = await make_scenario()
        spec = await self._paid(character_trait_specialty_factory, s)
        stale = await CharacterTraitSpecialty.get(id=spec.id)

        # When both copies are removed
        await self._remove(s, spec)
        await self._remove(s, stale)

        # Then the cost is refunded only once
        assert await _xp(s) == 5 + SPECIALTY_XP_COST

    async def test_remove_starting_points_refund_uses_stored_balance(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify a refund to a stale character adds to the stored balance."""
        # Given a character read at 1 point while 7 are stored, and a paid specialty
        s = await make_scenario(starting_points=1)
        await Character.filter(id=s.character.id).update(starting_points=7)
        spec = await self._paid(
            character_trait_specialty_factory, s, TraitModifyCurrency.STARTING_POINTS
        )

        # When removed
        await self._remove(s, spec)

        # Then the stored balance receives the refund and the instance matches it
        assert (await Character.get(id=s.character.id)).starting_points == 7 + SPECIALTY_XP_COST
        assert s.character.starting_points == 7 + SPECIALTY_XP_COST


class TestSpecialtiesAtZeroValue:
    """Test specialty refunds and deletion when an ability reaches 0."""

    async def _lower_to_zero(
        self, s: Scenario, currency: TraitModifyCurrency, recoup_store: MemoryStore | None = None
    ) -> None:
        await s.svc.modify_trait_value(
            company=s.company,
            user=s.user,
            character=s.character,
            character_trait=s.char_trait,
            target_value=0,
            currency=currency,
            recoup_store=recoup_store,
        )

    async def _paid(self, factory, s: Scenario) -> CharacterTraitSpecialty:
        return await factory(
            character_trait=s.char_trait,
            name="Sniping",
            cost_paid=SPECIALTY_XP_COST,
            currency_paid=TraitModifyCurrency.XP,
        )

    async def test_lowering_to_zero_with_xp_refunds_dots_and_specialty(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify an XP drop to 0 refunds the dots and the specialty."""
        # Given an ability at 1 with a paid specialty
        s = await make_scenario(value=1)
        await self._paid(character_trait_specialty_factory, s)
        savings = (await s.svc.calculate_all_downgrade_savings(s.char_trait))["1"]

        # When lowering to 0 with XP
        await self._lower_to_zero(s, TraitModifyCurrency.XP, MemoryStore())

        # Then XP rises by the dot savings plus the specialty cost and the rows are gone
        assert await _xp(s) == 5 + savings + SPECIALTY_XP_COST
        assert not await CharacterTraitSpecialty.filter(character_trait_id=s.char_trait.id).exists()

    async def test_lowering_to_zero_no_cost_still_refunds_specialty(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify a NO_COST drop to 0 still refunds the specialty."""
        # Given an ability at 1 with a paid specialty
        s = await make_scenario(value=1)
        await self._paid(character_trait_specialty_factory, s)

        # When lowering to 0 at no cost
        await self._lower_to_zero(s, TraitModifyCurrency.NO_COST)

        # Then only the specialty cost returns
        assert await _xp(s) == 5 + SPECIALTY_XP_COST

    async def test_lowering_to_zero_recoup_denied_xp_is_refused(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify DENIED recoup refuses an XP drop to 0 and keeps the specialty."""
        # Given DENIED recoup and a paid specialty
        s = await make_scenario(value=1, recoup=PermissionsRecoupXP.DENIED)
        await self._paid(character_trait_specialty_factory, s)

        # When lowering to 0 with XP
        # Then it is refused and the specialty remains
        with pytest.raises(PermissionDeniedError):
            await self._lower_to_zero(s, TraitModifyCurrency.XP, MemoryStore())
        assert await CharacterTraitSpecialty.filter(character_trait_id=s.char_trait.id).exists()

    async def test_lowering_to_zero_recoup_denied_no_cost_removes_without_refund(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify DENIED recoup removes the specialty without XP at no cost."""
        # Given DENIED recoup and a paid specialty
        s = await make_scenario(value=1, recoup=PermissionsRecoupXP.DENIED)
        await self._paid(character_trait_specialty_factory, s)

        # When lowering to 0 at no cost
        await self._lower_to_zero(s, TraitModifyCurrency.NO_COST)

        # Then the specialty is gone and XP is unchanged
        assert not await CharacterTraitSpecialty.filter(character_trait_id=s.char_trait.id).exists()
        assert await _xp(s) == 5

    async def test_lowering_to_one_keeps_specialties(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify dropping to 1 keeps specialties."""
        # Given an ability at 2 with a specialty
        s = await make_scenario(value=2)
        await self._paid(character_trait_specialty_factory, s)

        # When lowering to 1
        await s.svc.modify_trait_value(
            company=s.company,
            user=s.user,
            character=s.character,
            character_trait=s.char_trait,
            target_value=1,
            currency=TraitModifyCurrency.NO_COST,
        )

        # Then the specialty remains and nothing is refunded
        assert await CharacterTraitSpecialty.filter(character_trait_id=s.char_trait.id).exists()
        assert await _xp(s) == 5

    async def test_delete_trait_without_currency_refunds_specialties(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify deleting a trait with no currency refunds its specialties."""
        # Given an ability with a paid specialty
        s = await make_scenario(value=1)
        await self._paid(character_trait_specialty_factory, s)

        # When deleting the trait with no currency
        await s.svc.delete_trait(
            company=s.company,
            user=s.user,
            character=s.character,
            character_trait=s.char_trait,
            currency=None,
        )

        # Then the specialty cost returns and everything is gone
        assert await _xp(s) == 5 + SPECIALTY_XP_COST
        assert not await CharacterTrait.filter(id=s.char_trait.id).exists()
        assert not await CharacterTraitSpecialty.filter(character_trait_id=s.char_trait.id).exists()

    async def test_value_options_include_specialty_refund_at_zero(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify the zero and DELETE options include the specialty refund."""
        # Given an ability at 1 with a paid specialty
        s = await make_scenario(value=1)
        await self._paid(character_trait_specialty_factory, s)
        savings = (await s.svc.calculate_all_downgrade_savings(s.char_trait))["1"]

        # When fetching options
        result = await s.svc.get_value_options(character=s.character, character_trait=s.char_trait)

        # Then both zero options include the refund while point_change is dots-only
        expected = 5 + savings + SPECIALTY_XP_COST
        assert result.options["0"].xp_after == expected
        assert result.options["DELETE"].xp_after == expected
        assert result.options["0"].point_change == savings

    async def test_after_save_records_removed_specialty_names(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify the service records the names of specialties removed at 0."""
        # Given an ability at 1 with a specialty
        s = await make_scenario(value=1)
        await self._paid(character_trait_specialty_factory, s)

        # When lowering to 0
        await self._lower_to_zero(s, TraitModifyCurrency.NO_COST)

        # Then the removed names are recorded
        assert s.svc.removed_specialty_names == ["Sniping"]

    async def test_delete_trait_with_currency_keeps_removed_names(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify deleting with XP refunds once and keeps the removed names."""
        # Given an ability at 1 with a paid specialty
        s = await make_scenario(value=1)
        await self._paid(character_trait_specialty_factory, s)
        savings = (await s.svc.calculate_all_downgrade_savings(s.char_trait))["1"]

        # When deleting the trait with XP
        await s.svc.delete_trait(
            company=s.company,
            user=s.user,
            character=s.character,
            character_trait=s.char_trait,
            currency=TraitModifyCurrency.XP,
            recoup_store=MemoryStore(),
        )

        # Then the specialty is refunded once and its name is retained
        assert await _xp(s) == 5 + savings + SPECIALTY_XP_COST
        assert s.svc.removed_specialty_names == ["Sniping"]

    async def test_lowering_to_zero_response_has_no_specialties(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify the trait returned after dropping to 0 no longer lists its specialties."""
        # Given an ability at 1 with a specialty, loaded the way the request provider loads it
        s = await make_scenario(value=1)
        await self._paid(character_trait_specialty_factory, s)
        char_trait = (
            await CharacterTrait.filter(id=s.char_trait.id)
            .prefetch_related(*CHARACTER_TRAIT_PREFETCH)
            .first()
        )

        # When lowering to 0
        result = await s.svc.modify_trait_value(
            company=s.company,
            user=s.user,
            character=s.character,
            character_trait=char_trait,
            target_value=0,
            currency=TraitModifyCurrency.NO_COST,
        )

        # Then the serialized trait has no specialties
        response = CharacterTraitResponse.from_model(result)
        assert response.value == 0
        assert response.specialties == []

    async def test_failed_specialty_refund_rolls_back_value_change(
        self, make_scenario, character_trait_specialty_factory, mocker
    ) -> None:
        """Verify the value change is undone when clearing specialties fails."""
        # Given an ability at 1 with a paid specialty and a refund that fails
        s = await make_scenario(value=1)
        await self._paid(character_trait_specialty_factory, s)
        mocker.patch.object(
            CharacterTraitService,
            "_refund_specialty",
            autospec=True,
            side_effect=RuntimeError("boom"),
        )

        # When lowering to 0
        with pytest.raises(RuntimeError):
            await self._lower_to_zero(s, TraitModifyCurrency.NO_COST)

        # Then the value and the specialty are unchanged
        assert (await CharacterTrait.get(id=s.char_trait.id)).value == 1
        assert await CharacterTraitSpecialty.filter(character_trait_id=s.char_trait.id).exists()

    async def test_failed_trait_delete_rolls_back_specialty_refund(
        self, make_scenario, character_trait_specialty_factory, mocker
    ) -> None:
        """Verify specialties are not refunded when the trait delete fails."""
        # Given an ability with a paid specialty whose delete fails
        s = await make_scenario(value=1)
        await self._paid(character_trait_specialty_factory, s)
        mocker.patch.object(s.char_trait, "delete", autospec=True, side_effect=RuntimeError("boom"))

        # When deleting the trait
        with pytest.raises(RuntimeError):
            await s.svc.delete_trait(
                company=s.company,
                user=s.user,
                character=s.character,
                character_trait=s.char_trait,
                currency=None,
            )

        # Then the specialty and its cost are untouched
        assert await CharacterTraitSpecialty.filter(character_trait_id=s.char_trait.id).exists()
        assert await _xp(s) == 5

    async def test_reused_service_does_not_report_stale_removed_names(
        self, make_scenario, character_trait_specialty_factory, character_trait_factory
    ) -> None:
        """Verify each call reports only the specialties it removed."""
        # Given a service that already removed a specialty while lowering an ability to 0
        s = await make_scenario(value=1)
        await self._paid(character_trait_specialty_factory, s)
        await self._lower_to_zero(s, TraitModifyCurrency.NO_COST)
        assert s.svc.removed_specialty_names == ["Sniping"]
        other_trait = (
            await Trait.filter(
                sheet_section__name="Abilities", is_archived=False, custom_for_character_id=None
            )
            .offset(1)
            .first()
        )
        other = await character_trait_factory(character=s.character, trait=other_trait, value=1)

        # When the same service deletes another trait that has no specialties
        await s.svc.delete_trait(
            company=s.company,
            user=s.user,
            character=s.character,
            character_trait=other,
            currency=None,
        )

        # Then no removed names are reported
        assert s.svc.removed_specialty_names == []

    async def test_unchanged_value_does_not_report_stale_removed_names(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify a no-op value change clears names recorded by an earlier call."""
        # Given a service that already removed a specialty while lowering an ability to 0
        s = await make_scenario(value=1)
        await self._paid(character_trait_specialty_factory, s)
        await self._lower_to_zero(s, TraitModifyCurrency.NO_COST)

        # When the same service sets the value it already has
        await self._lower_to_zero(s, TraitModifyCurrency.NO_COST)

        # Then no removed names are reported
        assert s.svc.removed_specialty_names == []

    async def test_lowering_to_zero_refunds_starting_points_specialty(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify a specialty paid with starting points returns them when the ability hits 0."""
        # Given an ability at 1 with a specialty paid in starting points
        s = await make_scenario(value=1, starting_points=1)
        await character_trait_specialty_factory(
            character_trait=s.char_trait,
            name="Sniping",
            cost_paid=SPECIALTY_XP_COST,
            currency_paid=TraitModifyCurrency.STARTING_POINTS,
        )

        # When lowering to 0 at no cost
        await self._lower_to_zero(s, TraitModifyCurrency.NO_COST)

        # Then the starting points return and XP is untouched
        await s.character.refresh_from_db()
        assert s.character.starting_points == 1 + SPECIALTY_XP_COST
        assert await _xp(s) == 5

    async def test_value_options_include_starting_points_specialty_refund(
        self, make_scenario, character_trait_specialty_factory
    ) -> None:
        """Verify the zero and DELETE options add a starting-point specialty refund."""
        # Given an ability at 1 with a specialty paid in starting points
        s = await make_scenario(value=1, starting_points=1)
        await character_trait_specialty_factory(
            character_trait=s.char_trait,
            name="Sniping",
            cost_paid=SPECIALTY_XP_COST,
            currency_paid=TraitModifyCurrency.STARTING_POINTS,
        )
        savings = (await s.svc.calculate_all_downgrade_savings(s.char_trait))["1"]

        # When fetching options
        result = await s.svc.get_value_options(character=s.character, character_trait=s.char_trait)

        # Then starting points include the refund and XP excludes it
        expected = 1 + savings + SPECIALTY_XP_COST
        assert result.options["0"].starting_points_after == expected
        assert result.options["DELETE"].starting_points_after == expected
        assert result.options["0"].xp_after == 5 + savings
