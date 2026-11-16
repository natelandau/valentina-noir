"""Unit tests for CompanyService.update_settings."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from vapi.constants import (
    PermissionManageCampaign,
    PermissionManageNPC,
    PermissionsFreeTraitChanges,
    PermissionsGrantXP,
    PermissionsRecoupXP,
    SpecialtyRules,
    TraitModifyCurrency,
)
from vapi.db.sql_models.character import CharacterTraitSpecialty
from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.company import CompanySettings
from vapi.db.sql_models.user import CampaignExperience
from vapi.domain.controllers.company.dto import CompanySettingsPatch
from vapi.domain.services import CompanyService

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


class TestApplySettingsPatchScalars:
    """Test scalar field change tracking."""

    async def test_scalar_fields_return_diffs_with_settings_prefix(
        self,
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify scalar field changes return diffs keyed with 'settings.' prefix."""
        # Given a company with default settings
        company = await company_factory()
        settings = await CompanySettings.filter(company=company).first()

        # When patching scalar fields to new values
        patch = CompanySettingsPatch(
            character_autogen_xp_cost=20,
            character_autogen_num_choices=5,
            character_autogen_starting_points=25,
        )
        changes = await CompanyService().update_settings(settings=settings, patch=patch)

        # Then changes are returned with dotted prefix keys
        assert "settings.character_autogen_xp_cost" in changes
        assert changes["settings.character_autogen_xp_cost"]["old"] == 10
        assert changes["settings.character_autogen_xp_cost"]["new"] == 20
        assert "settings.character_autogen_num_choices" in changes
        assert changes["settings.character_autogen_num_choices"]["old"] == 3
        assert changes["settings.character_autogen_num_choices"]["new"] == 5
        assert "settings.character_autogen_starting_points" in changes
        assert changes["settings.character_autogen_starting_points"]["old"] == 0
        assert changes["settings.character_autogen_starting_points"]["new"] == 25

        # And the model is updated in-place
        assert settings.character_autogen_xp_cost == 20
        assert settings.character_autogen_num_choices == 5
        assert settings.character_autogen_starting_points == 25


class TestApplySettingsPatchStartingPoints:
    """Test character_autogen_starting_points change tracking."""

    async def test_starting_points_only_change(
        self,
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify patching only starting_points records the diff and updates the model."""
        # Given a company with default settings (starting_points=0)
        company = await company_factory()
        settings = await CompanySettings.filter(company=company).first()

        # When patching only starting_points
        patch = CompanySettingsPatch(character_autogen_starting_points=50)
        changes = await CompanyService().update_settings(settings=settings, patch=patch)

        # Then the diff contains only the starting_points change
        assert list(changes.keys()) == ["settings.character_autogen_starting_points"]
        assert changes["settings.character_autogen_starting_points"]["old"] == 0
        assert changes["settings.character_autogen_starting_points"]["new"] == 50
        assert settings.character_autogen_starting_points == 50


class TestApplySettingsPatchEnums:
    """Test enum field change tracking."""

    async def test_enum_field_changes_return_correct_enum_values(
        self,
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify enum field changes are applied and diffs contain enum instances."""
        # Given a company with default settings (UNRESTRICTED)
        company = await company_factory()
        settings = await CompanySettings.filter(company=company).first()

        # When patching permission_manage_campaign to a different value
        patch = CompanySettingsPatch(
            permission_manage_campaign=PermissionManageCampaign.STORYTELLER
        )
        changes = await CompanyService().update_settings(settings=settings, patch=patch)

        # Then the change is recorded with enum values
        assert "settings.permission_manage_campaign" in changes
        assert (
            changes["settings.permission_manage_campaign"]["old"]
            == PermissionManageCampaign.UNRESTRICTED
        )
        assert (
            changes["settings.permission_manage_campaign"]["new"]
            == PermissionManageCampaign.STORYTELLER
        )

        # And the model is updated
        assert settings.permission_manage_campaign == PermissionManageCampaign.STORYTELLER


class TestApplySettingsPatchNoOp:
    """Test no-op patch behavior."""

    async def test_same_values_return_empty_dict(
        self,
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify patching with current values returns no changes."""
        # Given a company with default settings
        company = await company_factory()
        settings = await CompanySettings.filter(company=company).first()

        # When patching with values identical to current settings
        patch = CompanySettingsPatch(
            character_autogen_xp_cost=10,
            character_autogen_num_choices=3,
            character_autogen_starting_points=0,
        )
        changes = await CompanyService().update_settings(settings=settings, patch=patch)

        # Then no changes are recorded
        assert changes == {}


class TestApplySettingsPatchUnset:
    """Test UNSET field skipping."""

    async def test_unset_fields_are_skipped(
        self,
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify UNSET fields do not appear in the diff or modify the model."""
        # Given a company with default settings
        company = await company_factory()
        settings = await CompanySettings.filter(company=company).first()
        original_xp_cost = settings.character_autogen_xp_cost

        # When patching only num_choices (xp_cost is UNSET)
        patch = CompanySettingsPatch(character_autogen_num_choices=7)
        changes = await CompanyService().update_settings(settings=settings, patch=patch)

        # Then xp_cost is not in the diff and is unchanged
        assert "settings.character_autogen_xp_cost" not in changes
        assert settings.character_autogen_xp_cost == original_xp_cost
        assert "settings.character_autogen_num_choices" in changes
        assert changes["settings.character_autogen_num_choices"]["new"] == 7


class TestApplySettingsPatchMixed:
    """Test combined scalar and enum changes."""

    async def test_mixed_scalar_and_enum_changes(
        self,
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify scalar and enum changes are combined correctly in a single diff."""
        # Given a company with default settings
        company = await company_factory()
        settings = await CompanySettings.filter(company=company).first()

        # When patching both scalar and enum fields
        patch = CompanySettingsPatch(
            character_autogen_xp_cost=15,
            permission_grant_xp=PermissionsGrantXP.STORYTELLER,
            permission_free_trait_changes=PermissionsFreeTraitChanges.WITHIN_24_HOURS,
            permission_recoup_xp=PermissionsRecoupXP.UNRESTRICTED,
        )
        changes = await CompanyService().update_settings(settings=settings, patch=patch)

        # Then all changed fields appear in the diff
        assert "settings.character_autogen_xp_cost" in changes
        assert changes["settings.character_autogen_xp_cost"]["new"] == 15
        assert "settings.permission_grant_xp" in changes
        assert changes["settings.permission_grant_xp"]["new"] == PermissionsGrantXP.STORYTELLER
        assert "settings.permission_free_trait_changes" in changes
        assert (
            changes["settings.permission_free_trait_changes"]["new"]
            == PermissionsFreeTraitChanges.WITHIN_24_HOURS
        )
        assert "settings.permission_recoup_xp" in changes
        assert changes["settings.permission_recoup_xp"]["new"] == PermissionsRecoupXP.UNRESTRICTED

        # And unset fields are absent
        assert "settings.character_autogen_num_choices" not in changes
        assert "settings.permission_manage_campaign" not in changes


class TestApplySettingsPatchManageNpc:
    """Test permission_manage_npc change tracking."""

    async def test_manage_npc_change_is_tracked(
        self,
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify patching permission_manage_npc records the diff and updates the model."""
        # Given a company with default settings (UNRESTRICTED)
        company = await company_factory()
        settings = await CompanySettings.filter(company=company).first()

        # When patching permission_manage_npc to STORYTELLER
        patch = CompanySettingsPatch(permission_manage_npc=PermissionManageNPC.STORYTELLER)
        changes = await CompanyService().update_settings(settings=settings, patch=patch)

        # Then the change is tracked and applied to the model as an enum
        assert changes["settings.permission_manage_npc"]["old"] == PermissionManageNPC.UNRESTRICTED
        assert changes["settings.permission_manage_npc"]["new"] == PermissionManageNPC.STORYTELLER
        assert settings.permission_manage_npc == PermissionManageNPC.STORYTELLER


class TestPermissionManageNpcDefault:
    """Test the default value of the permission_manage_npc setting."""

    async def test_default_permission_manage_npc_is_unrestricted(
        self,
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify a new company's settings default permission_manage_npc to UNRESTRICTED."""
        # Given a company created with default settings
        company = await company_factory()

        # When the settings are loaded
        settings = await CompanySettings.filter(company=company).first()

        # Then permission_manage_npc defaults to UNRESTRICTED
        assert settings.permission_manage_npc == PermissionManageNPC.UNRESTRICTED


class TestApplySettingsPatchSpecialtyXpCost:
    """Test the specialty_xp_cost_enabled boolean setting."""

    async def test_specialty_xp_cost_enabled_persists(
        self,
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify patching specialty_xp_cost_enabled persists and is reported as a change."""
        # Given a company with default settings
        company = await company_factory()
        settings = await CompanySettings.filter(company=company).first()

        # When enabling the setting
        changes = await CompanyService().update_settings(
            settings=settings, patch=CompanySettingsPatch(specialty_xp_cost_enabled=True)
        )

        # Then the change is reported and persisted
        assert changes["settings.specialty_xp_cost_enabled"] == {"old": False, "new": True}
        refreshed = await CompanySettings.get(id=settings.id)
        assert refreshed.specialty_xp_cost_enabled is True


class TestApplySettingsPatchSpecialtyRules:
    """Test that changing specialty rules removes the specialties they no longer allow."""

    async def test_switching_rules_removes_and_refunds_ineligible_specialties(
        self,
        company_factory: Callable[..., Any],
        user_factory: Callable[..., Any],
        campaign_factory: Callable[..., Any],
        character_factory: Callable[..., Any],
        character_trait_factory: Callable[..., Any],
        character_trait_specialty_factory: Callable[..., Any],
        campaign_experience_factory: Callable[..., Any],
    ) -> None:
        """Verify a switch to RATING_BASED removes a specialty on an ability below four."""
        # Given a FIXED_COST company with DENIED recoup and a player's Firearms at 2
        # holding a specialty bought for 3 XP
        company = await company_factory(
            settings__permission_recoup_xp=PermissionsRecoupXP.DENIED,
        )
        user = await user_factory(company=company)
        campaign = await campaign_factory(company=company)
        character = await character_factory(company=company, user_player=user, campaign=campaign)
        await campaign_experience_factory(user=user, campaign=campaign, xp_current=0, xp_total=0)
        firearms = await Trait.get(
            sheet_section__name="Abilities",
            name="Firearms",
            is_archived=False,
            custom_for_character_id=None,
        )
        char_trait = await character_trait_factory(character=character, trait=firearms, value=2)
        await character_trait_specialty_factory(
            character_trait=char_trait,
            name="Sniping",
            cost_paid=3,
            currency_paid=TraitModifyCurrency.XP,
        )
        settings = await CompanySettings.get(company=company)

        # When patching the rules to RATING_BASED
        changes = await CompanyService().update_settings(
            settings=settings,
            patch=CompanySettingsPatch(specialty_rules=SpecialtyRules.RATING_BASED),
        )

        # Then the change is recorded, the specialty is gone, and its XP returns in full
        assert changes["settings.specialty_rules"]["new"] == SpecialtyRules.RATING_BASED
        assert not await CharacterTraitSpecialty.filter(character_trait_id=char_trait.id).exists()
        experience = await CampaignExperience.get(user_id=user.id, campaign_id=campaign.id)
        assert experience.xp_current == 3


class TestApplySettingsPatchCustomFlawXpCost:
    """Test the custom_flaw_xp_cost integer setting."""

    async def test_custom_flaw_xp_cost_persists(
        self,
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify patching custom_flaw_xp_cost persists and is reported as a change."""
        # Given a company with default settings
        company = await company_factory()
        settings = await CompanySettings.filter(company=company).first()

        # When changing the setting
        changes = await CompanyService().update_settings(
            settings=settings, patch=CompanySettingsPatch(custom_flaw_xp_cost=5)
        )

        # Then the change is reported and persisted
        assert changes["settings.custom_flaw_xp_cost"] == {"old": 2, "new": 5}
        refreshed = await CompanySettings.get(id=settings.id)
        assert refreshed.custom_flaw_xp_cost == 5
