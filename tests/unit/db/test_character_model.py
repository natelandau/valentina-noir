"""Test character."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from beanie import PydanticObjectId

from vapi.constants import CharacterClass, CharacterStatus, GameVersion
from vapi.db.models import Character, CharacterConcept, CharacterTrait, Trait

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


@pytest.fixture
async def character_model() -> Character:
    """Base character."""
    return Character(
        character_class=CharacterClass.MORTAL,
        game_version=GameVersion.V4,
        name_first="  Foo  ",
        name_last="  Bar  ",
        name_nick="  Baz  ",
        company_id=PydanticObjectId(),
        user_creator_id=PydanticObjectId(),
        user_player_id=PydanticObjectId(),
        status=CharacterStatus.ALIVE,
        campaign_id=PydanticObjectId(),
    )


async def test_character_computed_fields(character_model: Character) -> None:
    """Test the character computed fields."""
    assert character_model.name == "Foo Bar"
    assert character_model.name_full == "Foo 'Baz' Bar"


class TestModelHooks:
    """Test the hooks on the character model."""

    async def test_character_delete_character_traits(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        character_trait_factory: Callable[[dict[str, Any]], CharacterTrait],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify that the character traits are deleted when the character is deleted."""
        # Given a character with character traits
        character = await character_factory()
        assert len(character.character_trait_ids) == 0
        traits = await Trait.find(Trait.is_archived == False).limit(3).to_list()
        for trait in traits:
            await character_trait_factory(character_id=character.id, trait=trait)

        await character.sync()
        assert len(character.character_trait_ids) == len(traits)

        # When the character is deleted
        await character.delete()

        # Then the character traits are deleted
        character_traits = await CharacterTrait.find(
            CharacterTrait.character_id == character.id
        ).to_list()

        assert not character_traits, (
            f"Character traits should be deleted when the character is deleted: {[x.id for x in character_traits]=}"
        )

    async def test_update_concept_name_on_save(
        self,
        character_factory: Callable[..., Character],
    ) -> None:
        """Verify concept_name is synced from the linked CharacterConcept on save."""
        # Given a character concept
        concept = await CharacterConcept.find_one()
        assert concept is not None

        # Given a character with that concept_id but no concept_name
        character = await character_factory(concept_id=concept.id)

        # Then the concept_name is populated from the concept
        assert character.concept_name == concept.name

    async def test_update_concept_name_when_concept_changes(
        self,
        character_factory: Callable[..., Character],
    ) -> None:
        """Verify concept_name updates when the linked concept's name changes."""
        # Given a character linked to a concept
        concept = await CharacterConcept.find_one()
        assert concept is not None
        character = await character_factory(concept_id=concept.id)
        assert character.concept_name == concept.name

        # When the concept's name changes and the character is saved
        concept.name = "Warrior"
        await concept.save()
        await character.save()

        # Then the concept_name reflects the new name
        assert character.concept_name == "Warrior"

    async def test_update_concept_name_skipped_when_no_concept_id(
        self,
        character_factory: Callable[..., Character],
    ) -> None:
        """Verify concept_name is unchanged when concept_id is None."""
        # Given a character with no concept_id and an arbitrary concept_name
        character = await character_factory(concept_id=None, concept_name="Stale Name")

        # Then the hook does not modify concept_name
        assert character.concept_name == "Stale Name"
