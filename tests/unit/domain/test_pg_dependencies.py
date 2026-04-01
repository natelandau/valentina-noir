"""Unit tests for Tortoise-based dependency providers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from uuid_utils import uuid7

from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import (
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)
from vapi.domain import pg_deps
from vapi.lib.exceptions import NotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


class TestProvideCharacterBlueprintSectionById:
    """Test provide_character_blueprint_section_by_id dependency."""

    async def test_returns_section_when_found(self) -> None:
        """Verify returning a character sheet section when found by ID."""
        # Given a section exists (from bootstrap)
        section = await CharSheetSection.filter(is_archived=False).first()

        # When we provide the section by ID
        result = await pg_deps.provide_character_blueprint_section_by_id(section.id)

        # Then the section is returned
        assert result.id == section.id
        assert result.name == section.name

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when section does not exist."""
        with pytest.raises(NotFoundError, match="Character sheet section not found"):
            await pg_deps.provide_character_blueprint_section_by_id(uuid7())


class TestProvideTraitCategoryById:
    """Test provide_trait_category_by_id dependency."""

    async def test_returns_category_when_found(self) -> None:
        """Verify returning a trait category with prefetched sheet_section."""
        # Given a category exists (from bootstrap)
        category = await TraitCategory.filter(is_archived=False).first()

        # When we provide the category by ID
        result = await pg_deps.provide_trait_category_by_id(category.id)

        # Then the category is returned with sheet_section prefetched
        assert result.id == category.id
        assert result.sheet_section is not None
        assert result.sheet_section.name is not None

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when category does not exist."""
        with pytest.raises(NotFoundError, match="Trait category not found"):
            await pg_deps.provide_trait_category_by_id(uuid7())


class TestProvideTraitSubcategoryById:
    """Test provide_trait_subcategory_by_id dependency."""

    async def test_returns_subcategory_when_found(self) -> None:
        """Verify returning a trait subcategory with prefetched relations."""
        # Given a subcategory exists (from bootstrap)
        subcategory = await TraitSubcategory.filter(is_archived=False).first()

        # When we provide the subcategory by ID
        result = await pg_deps.provide_trait_subcategory_by_id(subcategory.id)

        # Then the subcategory is returned with relations prefetched
        assert result.id == subcategory.id
        assert result.category is not None

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when subcategory does not exist."""
        with pytest.raises(NotFoundError, match="Trait subcategory not found"):
            await pg_deps.provide_trait_subcategory_by_id(uuid7())


class TestProvideTraitById:
    """Test provide_trait_by_id dependency."""

    async def test_returns_trait_when_found(self) -> None:
        """Verify returning a trait with prefetched relations."""
        # Given a trait exists (from bootstrap)
        trait = await Trait.filter(is_archived=False).first()

        # When we provide the trait by ID
        result = await pg_deps.provide_trait_by_id(trait.id)

        # Then the trait is returned with category and sheet_section prefetched
        assert result.id == trait.id
        assert result.category is not None
        assert result.sheet_section is not None

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when trait does not exist."""
        with pytest.raises(NotFoundError, match="Trait not found"):
            await pg_deps.provide_trait_by_id(uuid7())

    async def test_raises_not_found_when_archived(
        self, pg_trait_factory: Callable[..., Trait]
    ) -> None:
        """Verify raising NotFoundError when trait is archived."""
        # Given an archived trait exists
        trait = await pg_trait_factory(is_archived=True)

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Trait not found"):
            await pg_deps.provide_trait_by_id(trait.id)


class TestProvideCharacterConceptById:
    """Test provide_character_concept_by_id dependency."""

    async def test_returns_concept_when_found(self) -> None:
        """Verify returning a character concept when found by ID."""
        # Given a concept exists (from bootstrap)
        concept = await CharacterConcept.filter(is_archived=False).first()

        # When we provide the concept by ID
        result = await pg_deps.provide_character_concept_by_id(concept.id)

        # Then the concept is returned
        assert result.id == concept.id
        assert result.name == concept.name

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when concept does not exist."""
        with pytest.raises(NotFoundError, match="Character concept not found"):
            await pg_deps.provide_character_concept_by_id(uuid7())

    async def test_raises_not_found_when_archived(
        self, pg_character_concept_factory: Callable[..., CharacterConcept]
    ) -> None:
        """Verify raising NotFoundError when concept is archived."""
        # Given an archived concept exists
        concept = await pg_character_concept_factory(is_archived=True)

        # When/Then we expect a NotFoundError
        with pytest.raises(NotFoundError, match="Character concept not found"):
            await pg_deps.provide_character_concept_by_id(concept.id)


class TestProvideVampireClanById:
    """Test provide_vampire_clan_by_id dependency."""

    async def test_returns_clan_when_found(self) -> None:
        """Verify returning a vampire clan with prefetched disciplines."""
        # Given a clan exists (from bootstrap)
        clan = await VampireClan.filter(is_archived=False).first()

        # When we provide the clan by ID
        result = await pg_deps.provide_vampire_clan_by_id(clan.id)

        # Then the clan is returned with disciplines prefetched
        assert result.id == clan.id
        discipline_ids = [d.id for d in result.disciplines]
        assert isinstance(discipline_ids, list)

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when vampire clan does not exist."""
        with pytest.raises(NotFoundError, match="Vampire clan not found"):
            await pg_deps.provide_vampire_clan_by_id(uuid7())


class TestProvideWerewolfTribeById:
    """Test provide_werewolf_tribe_by_id dependency."""

    async def test_returns_tribe_when_found(self) -> None:
        """Verify returning a werewolf tribe with prefetched gifts."""
        # Given a tribe exists (from bootstrap)
        tribe = await WerewolfTribe.filter(is_archived=False).first()

        # When we provide the tribe by ID
        result = await pg_deps.provide_werewolf_tribe_by_id(tribe.id)

        # Then the tribe is returned with gifts prefetched
        assert result.id == tribe.id
        gift_ids = [g.id for g in result.gifts]
        assert isinstance(gift_ids, list)

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when werewolf tribe does not exist."""
        with pytest.raises(NotFoundError, match="Werewolf tribe not found"):
            await pg_deps.provide_werewolf_tribe_by_id(uuid7())


class TestProvideWerewolfAuspiceById:
    """Test provide_werewolf_auspice_by_id dependency."""

    async def test_returns_auspice_when_found(self) -> None:
        """Verify returning a werewolf auspice with prefetched gifts."""
        # Given an auspice exists (from bootstrap)
        auspice = await WerewolfAuspice.filter(is_archived=False).first()

        # When we provide the auspice by ID
        result = await pg_deps.provide_werewolf_auspice_by_id(auspice.id)

        # Then the auspice is returned with gifts prefetched
        assert result.id == auspice.id
        gift_ids = [g.id for g in result.gifts]
        assert isinstance(gift_ids, list)

    async def test_raises_not_found_when_missing(self) -> None:
        """Verify raising NotFoundError when werewolf auspice does not exist."""
        with pytest.raises(NotFoundError, match="Werewolf auspice not found"):
            await pg_deps.provide_werewolf_auspice_by_id(uuid7())
