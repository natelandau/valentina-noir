"""Unit tests for the company settings DTOs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import msgspec
import pytest

from vapi.db.sql_models.company import CompanySettings
from vapi.domain.controllers.company.dto import (
    CompanySettingsCreate,
    CompanySettingsPatch,
    CompanySettingsResponse,
)

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


async def test_company_settings_response_includes_specialty_xp_cost_enabled(
    company_factory: Callable[..., Any],
) -> None:
    """Verify the response exposes the specialty XP cost setting, defaulting to False."""
    # Given a company with default settings
    company = await company_factory()
    settings = await CompanySettings.get(company_id=company.id)

    # When converting to a response
    response = CompanySettingsResponse.from_model(settings)

    # Then the new setting defaults to False
    assert response.specialty_xp_cost_enabled is False


def test_company_settings_create_specialty_xp_cost_enabled_defaults_false() -> None:
    """Verify the create DTO defaults the specialty XP cost setting to False."""
    # Given / When an empty create body
    create = CompanySettingsCreate()

    # Then the field is False
    assert create.specialty_xp_cost_enabled is False


def test_company_settings_patch_specialty_xp_cost_enabled_defaults_unset() -> None:
    """Verify the patch DTO leaves the specialty XP cost setting unset by default."""
    # Given / When an empty patch
    patch = CompanySettingsPatch()

    # Then the field is UNSET
    assert patch.specialty_xp_cost_enabled is msgspec.UNSET
