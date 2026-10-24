"""Tests for the audit enrichment set by character trait controllers."""

from types import SimpleNamespace
from typing import Any

import pytest
from litestar.stores.memory import MemoryStore

from vapi.constants import TraitModifyCurrency, UserRole
from vapi.db.sql_models.character_sheet import Trait
from vapi.domain.controllers.character_trait.controllers import CharacterTraitController
from vapi.domain.controllers.character_trait.dto import (
    CharacterTraitSpecialtyUpdate,
    TraitModifyRequest,
)

pytestmark = pytest.mark.anyio


def _request() -> Any:
    """Build a request stand-in carrying only what the handlers read."""
    store = MemoryStore()
    return SimpleNamespace(
        state=SimpleNamespace(), app=SimpleNamespace(stores=SimpleNamespace(get=lambda _: store))
    )


@pytest.fixture
async def ability_with_specialty(
    company_factory,
    user_factory,
    character_factory,
    character_trait_factory,
    character_trait_specialty_factory,
) -> SimpleNamespace:
    """Create a company, admin user, character, and an ability at 1 with one specialty."""
    company = await company_factory()
    await company.fetch_related("settings")
    user = await user_factory(company=company, role=UserRole.ADMIN)
    character = await character_factory(company=company, user_player=user)
    trait = await Trait.filter(
        sheet_section__name="Abilities", is_archived=False, custom_for_character_id=None
    ).first()
    character_trait = await character_trait_factory(character=character, trait=trait, value=1)
    specialty = await character_trait_specialty_factory(
        character_trait=character_trait, name="Sniping"
    )
    return SimpleNamespace(
        company=company,
        user=user,
        character=character,
        character_trait=character_trait,
        specialty=specialty,
    )


async def test_modify_value_records_cleared_specialties(ability_with_specialty) -> None:
    """Verify lowering an ability to 0 records the removed specialties as an audit change."""
    # Given an ability at 1 with a specialty
    s = ability_with_specialty
    request = _request()

    # When lowering it to 0
    await CharacterTraitController.modify_value.fn(
        None,
        request=request,
        company=s.company,
        acting_user=s.user,
        character=s.character,
        character_trait=s.character_trait,
        data=TraitModifyRequest(target_value=0, currency=TraitModifyCurrency.NO_COST),
    )

    # Then the audit change lists the removed specialty
    assert request.state.audit_changes == {"specialties": {"old": ["Sniping"], "new": []}}


async def test_delete_character_trait_records_cleared_specialties(ability_with_specialty) -> None:
    """Verify deleting a trait records its removed specialties as an audit change."""
    # Given an ability with a specialty
    s = ability_with_specialty
    request = _request()

    # When deleting the trait
    await CharacterTraitController.delete_character_trait.fn(
        None,
        request=request,
        company=s.company,
        acting_user=s.user,
        character=s.character,
        character_trait=s.character_trait,
        currency=None,
    )

    # Then the audit change lists the removed specialty
    assert request.state.audit_changes == {"specialties": {"old": ["Sniping"], "new": []}}


async def test_update_specialty_records_name_change(ability_with_specialty) -> None:
    """Verify renaming a specialty records the old and new names as an audit change."""
    # Given an ability with a specialty
    s = ability_with_specialty
    request = _request()

    # When renaming the specialty
    await CharacterTraitController.update_specialty.fn(
        None,
        request=request,
        acting_user=s.user,
        character=s.character,
        character_trait=s.character_trait,
        specialty=s.specialty,
        data=CharacterTraitSpecialtyUpdate(name="Long Range"),
    )

    # Then the audit change records the rename
    assert request.state.audit_changes == {"name": {"old": "Sniping", "new": "Long Range"}}
