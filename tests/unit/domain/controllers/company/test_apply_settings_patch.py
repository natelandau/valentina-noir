"""Unit tests for _apply_settings_patch in the company controller."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from vapi.constants import (
    PermissionManageCampaign,
    PermissionsFreeTraitChanges,
    PermissionsGrantXP,
    PermissionsRecoupXP,
)
from vapi.db.sql_models.company import CompanySettings
from vapi.domain.controllers.company.controllers import _apply_settings_patch
from vapi.domain.controllers.company.dto import CompanySettingsPatch

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
        patch = CompanySettingsPatch(character_autogen_xp_cost=20, character_autogen_num_choices=5)
        changes = await _apply_settings_patch(settings, patch)

        # Then changes are returned with dotted prefix keys
        assert "settings.character_autogen_xp_cost" in changes
        assert changes["settings.character_autogen_xp_cost"]["old"] == 10
        assert changes["settings.character_autogen_xp_cost"]["new"] == 20
        assert "settings.character_autogen_num_choices" in changes
        assert changes["settings.character_autogen_num_choices"]["old"] == 3
        assert changes["settings.character_autogen_num_choices"]["new"] == 5

        # And the model is updated in-place
        assert settings.character_autogen_xp_cost == 20
        assert settings.character_autogen_num_choices == 5


class TestApplySettingsPatchEnums:
    """Test enum field change tracking."""

    async def test_enum_field_changes_return_correct_enum_values(
        self,
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify enum fields are wrapped correctly and diffs contain enum instances."""
        # Given a company with default settings (UNRESTRICTED)
        company = await company_factory()
        settings = await CompanySettings.filter(company=company).first()

        # When patching permission_manage_campaign to a different value
        patch = CompanySettingsPatch(permission_manage_campaign="STORYTELLER")
        changes = await _apply_settings_patch(settings, patch)

        # Then the change is recorded with the correct enum wrapper
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
        )
        changes = await _apply_settings_patch(settings, patch)

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
        changes = await _apply_settings_patch(settings, patch)

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
            permission_grant_xp="STORYTELLER",
            permission_free_trait_changes="WITHIN_24_HOURS",
            permission_recoup_xp="UNRESTRICTED",
        )
        changes = await _apply_settings_patch(settings, patch)

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
