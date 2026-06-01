"""Unit tests for CharacterService.reconcile_type_and_player."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import msgspec
import pytest

from vapi.constants import CharacterType
from vapi.domain.controllers.character.dto import CharacterPatch
from vapi.domain.services import CharacterService
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


class TestReconcileNonPlayerClearsPlayer:
    """NPC and STORYTELLER characters never keep a player."""

    @pytest.mark.parametrize("target_type", [CharacterType.NPC, CharacterType.STORYTELLER])
    async def test_reconcile_clears_provided_player_on_conversion(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
        target_type: CharacterType,
    ) -> None:
        """Verify converting a PLAYER to NPC/STORYTELLER with a player silently clears it."""
        # Given a PLAYER character and a patch converting it while still supplying a player
        company = await company_factory()
        character = await character_factory(company=company, type=CharacterType.PLAYER)
        service = CharacterService()
        data = CharacterPatch(type=target_type, user_player_id=uuid4())

        # When reconciling the patch
        service.reconcile_type_and_player(character, data)

        # Then the player is cleared instead of raising
        assert data.user_player_id is None

    @pytest.mark.parametrize("existing_type", [CharacterType.NPC, CharacterType.STORYTELLER])
    async def test_reconcile_clears_provided_player_without_type_change(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
        existing_type: CharacterType,
    ) -> None:
        """Verify a player provided on an already NPC/STORYTELLER character is cleared."""
        # Given an NPC/STORYTELLER character and a patch supplying a player but no type
        company = await company_factory()
        character = await character_factory(company=company, type=existing_type)
        service = CharacterService()
        data = CharacterPatch(user_player_id=uuid4())

        # When reconciling the patch
        service.reconcile_type_and_player(character, data)

        # Then the player is cleared
        assert data.user_player_id is None

    @pytest.mark.parametrize("existing_type", [CharacterType.NPC, CharacterType.STORYTELLER])
    async def test_reconcile_force_nulls_player_when_unset(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
        existing_type: CharacterType,
    ) -> None:
        """Verify a non-player character with no player in the patch is force-nulled."""
        # Given an NPC/STORYTELLER character and a patch that omits the player
        company = await company_factory()
        character = await character_factory(company=company, type=existing_type)
        service = CharacterService()
        data = CharacterPatch(name_first="Renamed")

        # When reconciling the patch
        service.reconcile_type_and_player(character, data)

        # Then user_player_id is explicitly set to None so apply_patch clears the column
        assert data.user_player_id is None


class TestReconcilePlayerRequiresPlayer:
    """PLAYER characters must always retain a player."""

    async def test_reconcile_rejects_clearing_player(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify clearing the player on a PLAYER character raises."""
        # Given a PLAYER character and a patch explicitly nulling the player
        company = await company_factory()
        character = await character_factory(company=company, type=CharacterType.PLAYER)
        service = CharacterService()
        data = CharacterPatch(user_player_id=None)

        # When reconciling the patch, Then it raises
        with pytest.raises(ValidationError, match="PLAYER characters must have a user_player_id"):
            service.reconcile_type_and_player(character, data)

    @pytest.mark.parametrize("source_type", [CharacterType.NPC, CharacterType.STORYTELLER])
    async def test_reconcile_rejects_conversion_to_player_without_player(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
        source_type: CharacterType,
    ) -> None:
        """Verify converting to PLAYER without supplying a player raises."""
        # Given an NPC/STORYTELLER character and a patch converting it to PLAYER with no player
        company = await company_factory()
        character = await character_factory(company=company, type=source_type)
        service = CharacterService()
        data = CharacterPatch(type=CharacterType.PLAYER)

        # When reconciling the patch, Then it raises
        with pytest.raises(
            ValidationError, match="Converting a character to PLAYER requires user_player_id"
        ):
            service.reconcile_type_and_player(character, data)

    async def test_reconcile_preserves_valid_player(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify a valid player on a PLAYER character is left untouched."""
        # Given a PLAYER character and a patch supplying a real player
        company = await company_factory()
        character = await character_factory(company=company, type=CharacterType.PLAYER)
        service = CharacterService()
        new_player_id = uuid4()
        data = CharacterPatch(user_player_id=new_player_id)

        # When reconciling the patch
        service.reconcile_type_and_player(character, data)

        # Then the player is preserved
        assert data.user_player_id == new_player_id

    async def test_reconcile_leaves_player_unset_when_omitted(
        self,
        character_factory: Callable[..., Any],
        company_factory: Callable[..., Any],
    ) -> None:
        """Verify a PLAYER patch that omits the player leaves it UNSET."""
        # Given a PLAYER character and a patch that does not mention the player
        company = await company_factory()
        character = await character_factory(company=company, type=CharacterType.PLAYER)
        service = CharacterService()
        data = CharacterPatch(name_first="Renamed")

        # When reconciling the patch
        service.reconcile_type_and_player(character, data)

        # Then the player remains UNSET and is not applied by apply_patch
        assert data.user_player_id is msgspec.UNSET
