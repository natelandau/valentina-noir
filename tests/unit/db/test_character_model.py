"""Test character."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from beanie import PydanticObjectId

from vapi.constants import CharacterClass, CharacterStatus, GameVersion
from vapi.db.models import Character, CharacterTrait, Trait

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
