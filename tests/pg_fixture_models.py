"""Fixtures for Tortoise ORM models.

Parallel to fixture_models.py (Beanie-based) during the migration. Once all domains
are migrated (Session 11), delete fixture_models.py and consolidate into this file.

Fixtures that create constant data (traits, concepts, etc.) must clean up after
themselves because the cleanup_pg_database fixture only deletes non-constant tables.
"""

from __future__ import annotations

from typing import Any

import pytest

from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import CharSheetSection, Trait, TraitCategory

pytestmark = pytest.mark.anyio


@pytest.fixture
async def pg_trait_factory():
    """Return a factory that creates Tortoise Trait instances and cleans up after the test.

    Traits are constant data preserved across tests, so the factory tracks
    created instances and deletes them when the test completes.
    """
    created: list[Trait] = []

    async def _factory(**kwargs: Any) -> Trait:
        if "category" not in kwargs and "category_id" not in kwargs:
            category = await TraitCategory.filter(is_archived=False).first()
            kwargs["category"] = category
        if "sheet_section" not in kwargs and "sheet_section_id" not in kwargs:
            category = kwargs.get("category") or await TraitCategory.get(id=kwargs["category_id"])
            section = await CharSheetSection.get(id=category.sheet_section_id)
            kwargs["sheet_section"] = section

        defaults: dict[str, Any] = {
            "name": "Test Trait",
            "min_value": 0,
            "max_value": 5,
            "show_when_zero": True,
            "initial_cost": 1,
            "upgrade_cost": 2,
            "is_custom": False,
            "custom_for_character_id": None,
            "is_archived": False,
        }
        defaults.update(kwargs)
        trait = await Trait.create(**defaults)
        created.append(trait)
        return trait

    yield _factory

    for trait in created:
        await trait.delete()


@pytest.fixture
async def pg_character_concept_factory():
    """Return a factory that creates Tortoise CharacterConcept instances with cleanup.

    Concepts are constant data preserved across tests, so the factory tracks
    created instances and deletes them when the test completes.
    """
    created: list[CharacterConcept] = []

    async def _factory(**kwargs: Any) -> CharacterConcept:
        defaults: dict[str, Any] = {
            "name": "Test Concept",
            "description": "Test description",
            "examples": ["Example 1", "Example 2"],
            "company_id": None,
            "is_archived": False,
        }
        defaults.update(kwargs)
        concept = await CharacterConcept.create(**defaults)
        created.append(concept)
        return concept

    yield _factory

    for concept in created:
        await concept.delete()
