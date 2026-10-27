"""Test the company settings backfill in migration 0027."""

import importlib

import pytest
from tortoise import Tortoise

from vapi.db.sql_models.company import CompanySettings

pytestmark = pytest.mark.anyio

migration = importlib.import_module("vapi.db.migrations.0027_backfill_company_settings")

_SETTINGS_FIELDS = (
    "character_autogen_xp_cost",
    "character_autogen_num_choices",
    "character_autogen_starting_points",
    "permission_manage_campaign",
    "permission_manage_npc",
    "permission_grant_xp",
    "permission_free_trait_changes",
    "permission_recoup_xp",
    "specialty_xp_cost_enabled",
)


async def _run_backfill() -> None:
    await Tortoise.get_connection("default").execute_script(migration.BACKFILL_COMPANY_SETTINGS_SQL)


async def test_backfill_creates_default_settings_for_company_without_any(company_factory) -> None:
    """Verify a company with no settings row gets one matching the model defaults."""
    # Given a company whose settings row is missing
    company = await company_factory()
    await CompanySettings.filter(company_id=company.id).delete()

    # When the backfill runs
    await _run_backfill()

    # Then one settings row exists with the same values a new CompanySettings would have
    settings = await CompanySettings.filter(company_id=company.id).all()
    defaults = CompanySettings()
    assert len(settings) == 1
    assert {f: getattr(settings[0], f) for f in _SETTINGS_FIELDS} == {
        f: getattr(defaults, f) for f in _SETTINGS_FIELDS
    }
    assert settings[0].is_archived is False


async def test_backfill_leaves_existing_settings_alone(company_factory) -> None:
    """Verify a company that already has settings keeps its row and values."""
    # Given a company with customized settings
    company = await company_factory(settings__character_autogen_xp_cost=25)
    before = await CompanySettings.get(company_id=company.id)

    # When the backfill runs
    await _run_backfill()

    # Then the original row is untouched
    after = await CompanySettings.filter(company_id=company.id).all()
    assert [s.id for s in after] == [before.id]
    assert after[0].character_autogen_xp_cost == 25
