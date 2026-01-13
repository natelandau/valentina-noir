"""Unit tests for the charactertrait db model."""

from collections.abc import Callable
from typing import Any

import pytest

from vapi.db.models import Character, CharacterTrait, Trait

pytestmark = pytest.mark.anyio


class TestModelHooks:
    """Test hooks on the database model."""

    async def test_sync_id_to_character_on_save(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify that the character's character trait id is removed from the character."""
        character = await character_factory()
        trait = await Trait.find_one(Trait.is_archived == False)

        # Add the character trait id to the character
        character_trait = await CharacterTrait(
            character_id=character.id, trait=trait, value=1
        ).insert()

        # Verify that the character trait id is added to the character
        await character.sync()

        assert character_trait.id in character.character_trait_ids
        assert len(character.character_trait_ids) == 1

    async def test_remove_id_from_character_on_delete(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify that the character trait id is removed from the character."""
        character = await character_factory()
        trait = await Trait.find_one(Trait.is_archived == False)
        character_trait = CharacterTrait(character_id=character.id, trait=trait, value=1)
        await character_trait.insert()
        await character.sync()
        if character_trait.id not in character.character_trait_ids:
            character.character_trait_ids.append(character_trait.id)
        await character.save()

        # Remove the character trait id from the character
        await character_trait.delete()

        # Verify that the character trait id is removed from the character
        await character.sync()
        assert character_trait.id not in character.character_trait_ids
        assert len(character.character_trait_ids) == 0

        await character.delete()
