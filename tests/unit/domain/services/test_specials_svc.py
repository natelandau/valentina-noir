"""Unit tests for character specials services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from vapi.db.models import (
    HunterEdge,
    HunterEdgePerk,
    WerewolfAuspice,
    WerewolfGift,
    WerewolfRite,
    WerewolfTribe,
)
from vapi.db.models.character import HunterAttributesEdgeModel, WerewolfAttributes
from vapi.domain.controllers.character_specials.dto import CharacterPerkDTO
from vapi.domain.services import (
    CharacterEdgeService,
    CharacterGiftsService,
    CharacterRitesService,
)
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.models import Character

pytestmark = pytest.mark.anyio


@pytest.fixture
async def get_mock_hunter_edge_and_perks(
    character_factory: Callable[[dict[str, Any]], Character],
) -> tuple[Character, HunterEdge, list[HunterEdgePerk]]:
    """Get mock data for hunter edge and perks.

    Returns a tuple of:
    - character: the character with the hunter edge and perks
    - hunter_edge: the edge added to the character
    - hunter_edge_perks: the perks added to the edge on the character
    """
    character = await character_factory(character_class="HUNTER")
    hunter_edge = await HunterEdge.find_one(HunterEdge.is_archived == False)
    hunter_edge_perks = (
        await HunterEdgePerk.find(
            HunterEdgePerk.is_archived == False, HunterEdgePerk.edge_id == hunter_edge.id
        )
        .limit(2)
        .to_list()
    )

    character_edge = HunterAttributesEdgeModel(
        edge_id=hunter_edge.id,
        perk_ids=[hunter_edge_perk.id for hunter_edge_perk in hunter_edge_perks],
    )

    character.hunter_attributes.edges = [character_edge]
    character.hunter_attributes.creed = "Creed"
    await character.save()

    return (
        character,
        hunter_edge,
        hunter_edge_perks,
    )


@pytest.fixture
async def werewolf_character(
    character_factory: Callable[[dict[str, Any]], Character],
) -> Character:
    """Get mock data for werewolf gifts and rites."""
    character = await character_factory(character_class="WEREWOLF")
    tribe = await WerewolfTribe.find_one(WerewolfTribe.is_archived == False)
    auspice = await WerewolfAuspice.find_one(WerewolfAuspice.is_archived == False)
    gift = await WerewolfGift.find_one(WerewolfGift.is_archived == False)
    rite = await WerewolfRite.find_one(WerewolfRite.is_archived == False)

    character.werewolf_attributes = WerewolfAttributes(
        tribe_id=tribe.id,
        tribe_name=tribe.name,
        auspice_id=auspice.id,
        auspice_name=auspice.name,
        gift_ids=[gift.id],
        rite_ids=[rite.id],
        total_renown=10,
    )
    await character.save()
    yield character
    await character.delete()


class TestCharacterEdgeService:
    """Test character edge service."""

    async def test_get_edge_and_perks_dto_by_id(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Test get edge and perks dto by id."""
        # given a character with a hunter edge and perks
        character, hunter_edge, hunter_edge_perks = get_mock_hunter_edge_and_perks

        # when we get the edge and perks dto by id
        service = CharacterEdgeService()
        edge_and_perks_dto = await service.get_edge_and_perks_dto_by_id(hunter_edge.id, character)

        # then we get a valid CharacterEdgeAndPerksDTO
        assert edge_and_perks_dto.name == hunter_edge.name
        assert edge_and_perks_dto.pool == hunter_edge.pool
        assert edge_and_perks_dto.system == hunter_edge.system
        assert edge_and_perks_dto.type == hunter_edge.type
        assert edge_and_perks_dto.description == hunter_edge.description
        assert edge_and_perks_dto.perks == [
            CharacterPerkDTO(
                id=hunter_edge_perk.id,
                name=hunter_edge_perk.name,
                description=hunter_edge_perk.description,
            )
            for hunter_edge_perk in hunter_edge_perks
        ]

    async def test_get_edge_and_perks_dto_by_id_no_hunter_attributes_error(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify validation error is raised when no hunter attributes."""
        # given a character with a hunter edge and perks
        character = await character_factory(character_class="MORTAL")
        edge = await HunterEdge.find_one(HunterEdge.is_archived == False)

        # when we get the edge and perks dto by id
        # then a validation error is raised
        service = CharacterEdgeService()
        with pytest.raises(ValidationError):
            await service.get_edge_and_perks_dto_by_id(edge.id, character, raise_on_not_found=True)

    async def test_get_edge_and_perks_dto_by_id_no_hunter_attributes_none(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify none is returned when no hunter attributes."""
        # given a character with a hunter edge and perks
        character = await character_factory(character_class="MORTAL")
        edge = await HunterEdge.find_one(HunterEdge.is_archived == False)

        # when we get the edge and perks dto by id
        # then none is returned
        service = CharacterEdgeService()
        assert not await service.get_edge_and_perks_dto_by_id(
            edge.id, character, raise_on_not_found=False
        )

    async def test_get_edge_and_perks_dto_by_id_not_found_error(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify validation error is raised when edge not found."""
        # given a character with a hunter edge and perks
        character, hunter_edge, _ = get_mock_hunter_edge_and_perks
        new_hunter_edge = await HunterEdge.find_one(
            HunterEdge.is_archived == False, HunterEdge.id != hunter_edge.id
        )

        # when we get the edge and perks dto by id
        # then a validation error is raised
        service = CharacterEdgeService()
        with pytest.raises(ValidationError):
            await service.get_edge_and_perks_dto_by_id(
                new_hunter_edge.id, character, raise_on_not_found=True
            )

    async def test_get_edge_and_perks_dto_by_id_not_found_none(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify none is returned when edge not found and raise_on_not_found is False."""
        # given a character with a hunter edge and perks
        character, hunter_edge, _ = get_mock_hunter_edge_and_perks
        new_hunter_edge = await HunterEdge.find_one(
            HunterEdge.is_archived == False, HunterEdge.id != hunter_edge.id
        )

        # when we get the edge and perks dto by id
        # then none is returned
        service = CharacterEdgeService()
        assert not await service.get_edge_and_perks_dto_by_id(
            new_hunter_edge.id, character, raise_on_not_found=False
        )

    async def test_add_edge_to_character_no_hunter_attributes(
        self, character_factory: Callable[[dict[str, Any]], Character], debug: Callable[[Any], None]
    ) -> None:
        """Test add edge to character with no pre-existing hunter attributes."""
        # given a character without hunter attributes
        character = await character_factory(character_class="MORTAL")
        hunter_edge = await HunterEdge.find_one(HunterEdge.is_archived == False)

        # when we add the edge to the character
        service = CharacterEdgeService()
        result = await service.add_edge_to_character(edge=hunter_edge, character=character)

        # then we get a valid CharacterEdgeAndPerksDTO
        assert character.hunter_attributes.edges == [
            HunterAttributesEdgeModel(edge_id=hunter_edge.id, perk_ids=[])
        ]
        assert result.name == hunter_edge.name
        assert result.pool == hunter_edge.pool
        assert result.system == hunter_edge.system
        assert result.type == hunter_edge.type
        assert result.description == hunter_edge.description
        assert result.perks == []

    async def test_add_edge_to_existing_hunter_attributes(
        self, character_factory: Callable[[dict[str, Any]], Character], debug: Callable[[Any], None]
    ) -> None:
        """Test add edge to existing character hunter attributes."""
        # given a character with hunter attributes
        character = await character_factory(character_class="HUNTER")
        hunter_edge = await HunterEdge.find_one(HunterEdge.is_archived == False)
        hunter_edge_perks = await HunterEdgePerk.find(
            HunterEdgePerk.is_archived == False, HunterEdgePerk.edge_id == hunter_edge.id
        ).to_list()

        character_edge = HunterAttributesEdgeModel(
            edge_id=hunter_edge.id,
            perk_ids=[hunter_edge_perk.id for hunter_edge_perk in hunter_edge_perks],
        )

        character.hunter_attributes.edges = [character_edge]
        character.hunter_attributes.creed = "Test Creed"
        await character.save()

        new_hunter_edge = await HunterEdge.find_one(
            HunterEdge.is_archived == False, HunterEdge.id != hunter_edge.id
        )

        # when we add the edge to the character
        service = CharacterEdgeService()
        result = await service.add_edge_to_character(edge=new_hunter_edge, character=character)

        # then we get a valid CharacterEdgeAndPerksDTO
        assert character.hunter_attributes.edges == [
            character_edge,
            HunterAttributesEdgeModel(edge_id=new_hunter_edge.id, perk_ids=[]),
        ]
        assert character.hunter_attributes.creed == "Test Creed"

        assert result.name == new_hunter_edge.name
        assert result.pool == new_hunter_edge.pool
        assert result.system == new_hunter_edge.system
        assert result.type == new_hunter_edge.type
        assert result.description == new_hunter_edge.description
        assert result.perks == []

    async def test_get_perk_dto_by_id(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify perk dto is returned when perk exists in character."""
        # given a character with a hunter edge and perks
        character, _, hunter_edge_perks = get_mock_hunter_edge_and_perks
        perk = hunter_edge_perks[0]

        # when we get the perk dto by id
        service = CharacterEdgeService()
        perk_dto = await service.get_perk_dto_by_id(perk.id, character)

        # then we get a valid CharacterPerkDTO
        assert perk_dto.id == perk.id
        assert perk_dto.name == perk.name
        assert perk_dto.description == perk.description

    async def test_get_perk_dto_by_id_no_hunter_attributes_error(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify validation error is raised when no hunter attributes."""
        # given a character without hunter attributes
        character = await character_factory(character_class="MORTAL")
        perk = await HunterEdgePerk.find_one(HunterEdgePerk.is_archived == False)

        # when we get the perk dto by id
        # then a validation error is raised
        service = CharacterEdgeService()
        with pytest.raises(ValidationError):
            await service.get_perk_dto_by_id(perk.id, character, raise_on_not_found=True)

    async def test_get_perk_dto_by_id_no_hunter_attributes_none(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify none is returned when no hunter attributes."""
        # given a character without hunter attributes
        character = await character_factory(character_class="MORTAL")
        perk = await HunterEdgePerk.find_one(HunterEdgePerk.is_archived == False)

        # when we get the perk dto by id
        # then none is returned
        service = CharacterEdgeService()
        assert not await service.get_perk_dto_by_id(perk.id, character, raise_on_not_found=False)

    async def test_get_perk_dto_by_id_not_found_error(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify validation error is raised when perk not found."""
        # given a character with a hunter edge and perks
        character, hunter_edge, _ = get_mock_hunter_edge_and_perks
        new_perk = await HunterEdgePerk.find_one(
            HunterEdgePerk.is_archived == False, HunterEdgePerk.edge_id != hunter_edge.id
        )

        # when we get the perk dto by id
        # then a validation error is raised
        service = CharacterEdgeService()
        with pytest.raises(ValidationError):
            await service.get_perk_dto_by_id(new_perk.id, character, raise_on_not_found=True)

    async def test_get_perk_dto_by_id_not_found_none(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify none is returned when perk not found."""
        # given a character with a hunter edge and perks
        character, hunter_edge, _ = get_mock_hunter_edge_and_perks
        new_perk = await HunterEdgePerk.find_one(
            HunterEdgePerk.is_archived == False, HunterEdgePerk.edge_id != hunter_edge.id
        )

        # when we get the perk dto by id
        # then none is returned
        service = CharacterEdgeService()
        assert not await service.get_perk_dto_by_id(
            new_perk.id, character, raise_on_not_found=False
        )

    async def test_remove_edge_from_character(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify edge is removed from character."""
        # given a character with a hunter edge and perks
        character, hunter_edge, _ = get_mock_hunter_edge_and_perks
        assert len(character.hunter_attributes.edges) == 1

        # when we remove the edge from the character
        service = CharacterEdgeService()
        await service.remove_edge_from_character(edge_id=hunter_edge.id, character=character)

        # then the edge is removed
        assert character.hunter_attributes.edges == []

    async def test_remove_edge_from_character_no_hunter_attributes(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify validation error is raised when no hunter attributes."""
        # given a character without hunter attributes
        character = await character_factory(character_class="MORTAL")
        hunter_edge = await HunterEdge.find_one(HunterEdge.is_archived == False)

        # when we remove the edge from the character
        # then a validation error is raised
        service = CharacterEdgeService()
        with pytest.raises(ValidationError):
            await service.remove_edge_from_character(edge_id=hunter_edge.id, character=character)

    async def test_remove_edge_from_character_edge_not_found(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify validation error is raised when edge not found."""
        # given a character with a hunter edge
        character, hunter_edge, _ = get_mock_hunter_edge_and_perks
        new_hunter_edge = await HunterEdge.find_one(
            HunterEdge.is_archived == False, HunterEdge.id != hunter_edge.id
        )

        # when we remove an edge that is not in the character
        # then a validation error is raised
        service = CharacterEdgeService()
        with pytest.raises(ValidationError):
            await service.remove_edge_from_character(
                edge_id=new_hunter_edge.id, character=character
            )

    async def test_remove_edge_from_character_no_hunter_attributes_no_error(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify no error is raised when no hunter attributes and raise_on_not_found is False."""
        # given a character without hunter attributes
        character = await character_factory(character_class="MORTAL")
        hunter_edge = await HunterEdge.find_one(HunterEdge.is_archived == False)

        # when we remove the edge from the character with raise_on_not_found=False
        # then no error is raised
        service = CharacterEdgeService()
        await service.remove_edge_from_character(
            edge_id=hunter_edge.id, character=character, raise_on_not_found=False
        )

    async def test_remove_edge_from_character_edge_not_found_no_error(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify no error is raised when edge not found and raise_on_not_found is False."""
        # given a character with a hunter edge
        character, hunter_edge, _ = get_mock_hunter_edge_and_perks
        new_hunter_edge = await HunterEdge.find_one(
            HunterEdge.is_archived == False, HunterEdge.id != hunter_edge.id
        )

        # when we remove an edge that is not in the character with raise_on_not_found=False
        # then no error is raised
        service = CharacterEdgeService()
        await service.remove_edge_from_character(
            edge_id=new_hunter_edge.id, character=character, raise_on_not_found=False
        )

    async def test_add_perk_to_edge_new_edge(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify perk is added to edge."""
        # given a character with a hunter edge and perks
        character, hunter_edge, hunter_edge_perks = get_mock_hunter_edge_and_perks
        new_edge = await HunterEdge.find_one(
            HunterEdge.is_archived == False, HunterEdge.id != hunter_edge.id
        )
        new_perk = await HunterEdgePerk.find_one(
            HunterEdgePerk.is_archived == False, HunterEdgePerk.edge_id != hunter_edge.id
        )

        # when we add the perk to the edge
        service = CharacterEdgeService()
        result = await service.add_perk_to_edge(perk=new_perk, edge=new_edge, character=character)

        # then we get a valid CharacterEdgeAndPerksDTO
        assert character.hunter_attributes.edges == [
            HunterAttributesEdgeModel(
                edge_id=hunter_edge.id, perk_ids=[perk.id for perk in hunter_edge_perks]
            ),
            HunterAttributesEdgeModel(edge_id=new_edge.id, perk_ids=[new_perk.id]),
        ]
        assert result.name == new_edge.name
        assert result.pool == new_edge.pool
        assert result.system == new_edge.system
        assert result.type == new_edge.type
        assert result.description == new_edge.description
        assert result.perks == [
            CharacterPerkDTO(
                id=new_perk.id,
                name=new_perk.name,
                description=new_perk.description,
            )
        ]

    async def test_add_perk_to_edge_existing_edge(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify perk is added to existing edge."""
        # given a character with a hunter edge and perks
        character, hunter_edge, hunter_edge_perks = get_mock_hunter_edge_and_perks
        new_perk = await HunterEdgePerk.find_one(
            HunterEdgePerk.is_archived == False,
            HunterEdgePerk.edge_id == hunter_edge.id,
            HunterEdgePerk.id != hunter_edge_perks[0].id,
            HunterEdgePerk.id != hunter_edge_perks[1].id,
        )

        # when we add the perk to the edge
        service = CharacterEdgeService()
        result = await service.add_perk_to_edge(
            perk=new_perk, edge=hunter_edge, character=character
        )

        # then we get a valid CharacterEdgeAndPerksDTO
        assert character.hunter_attributes.edges == [
            HunterAttributesEdgeModel(
                edge_id=hunter_edge.id,
                perk_ids=[perk.id for perk in hunter_edge_perks] + [new_perk.id],
            ),
        ]
        assert result.name == hunter_edge.name
        assert result.pool == hunter_edge.pool
        assert result.system == hunter_edge.system
        assert result.type == hunter_edge.type
        assert result.description == hunter_edge.description
        assert result.perks == [
            *[
                CharacterPerkDTO(
                    id=perk.id,
                    name=perk.name,
                    description=perk.description,
                )
                for perk in hunter_edge_perks
            ],
            CharacterPerkDTO(
                id=new_perk.id,
                name=new_perk.name,
                description=new_perk.description,
            ),
        ]

    async def test_add_perk_to_edge_not_on_character(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify perk is added to edge not on character."""
        # given a character without hunter attributes
        character = await character_factory(character_class="MORTAL")
        hunter_edge = await HunterEdge.find_one(HunterEdge.is_archived == False)
        new_perk = await HunterEdgePerk.find_one(
            HunterEdgePerk.is_archived == False, HunterEdgePerk.edge_id == hunter_edge.id
        )

        # when we add the perk to the edge not on the character
        service = CharacterEdgeService()
        result = await service.add_perk_to_edge(
            perk=new_perk, edge=hunter_edge, character=character
        )

        # then we get a valid CharacterEdgeAndPerksDTO
        assert character.hunter_attributes.edges == [
            HunterAttributesEdgeModel(edge_id=hunter_edge.id, perk_ids=[new_perk.id]),
        ]
        assert result.name == hunter_edge.name
        assert result.pool == hunter_edge.pool
        assert result.system == hunter_edge.system
        assert result.type == hunter_edge.type
        assert result.description == hunter_edge.description
        assert result.perks == [
            CharacterPerkDTO(
                id=new_perk.id,
                name=new_perk.name,
                description=new_perk.description,
            )
        ]

    async def test_add_perk_to_edge_perk_already_on_edge(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify no error is raised when perk already on edge."""
        # given a character with a hunter edge and perks
        character, hunter_edge, hunter_edge_perks = get_mock_hunter_edge_and_perks
        new_perk = hunter_edge_perks[0]

        # when we add the perk to the edge that is already on the character
        service = CharacterEdgeService()
        result = await service.add_perk_to_edge(
            perk=new_perk, edge=hunter_edge, character=character
        )

        # then we get a valid CharacterEdgeAndPerksDTO
        assert character.hunter_attributes.edges == [
            HunterAttributesEdgeModel(
                edge_id=hunter_edge.id, perk_ids=[perk.id for perk in hunter_edge_perks]
            ),
        ]
        assert result.name == hunter_edge.name
        assert result.pool == hunter_edge.pool
        assert result.system == hunter_edge.system
        assert result.type == hunter_edge.type
        assert result.description == hunter_edge.description
        assert result.perks == [
            CharacterPerkDTO(
                id=perk.id,
                name=perk.name,
                description=perk.description,
            )
            for perk in hunter_edge_perks
        ]

    async def test_add_perk_to_edge_perk_not_on_edge(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify validation error is raised when perk not found on edge."""
        # given a character with a hunter edge and perks
        character, hunter_edge, _ = get_mock_hunter_edge_and_perks
        new_perk = await HunterEdgePerk.find_one(
            HunterEdgePerk.is_archived == False, HunterEdgePerk.edge_id != hunter_edge.id
        )

        # when we add the perk to the edge that is not on the character
        service = CharacterEdgeService()
        with pytest.raises(ValidationError):
            await service.add_perk_to_edge(perk=new_perk, edge=hunter_edge, character=character)

    async def test_remove_perk_from_edge_perk_not_on_edge(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify validation error is raised when perk not found on edge."""
        # given a character with a hunter edge and perks
        character, hunter_edge, _ = get_mock_hunter_edge_and_perks
        new_perk = await HunterEdgePerk.find_one(
            HunterEdgePerk.is_archived == False, HunterEdgePerk.edge_id != hunter_edge.id
        )

        # when we remove the perk from the edge that is not on the character
        service = CharacterEdgeService()
        with pytest.raises(ValidationError):
            await service.remove_perk_from_edge(
                perk=new_perk, edge=hunter_edge, character=character
            )

    async def test_remove_perk_from_edge(
        self,
        get_mock_hunter_edge_and_perks: Callable[
            [], tuple[Character, HunterEdge, list[HunterEdgePerk]]
        ],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify perk is removed from edge."""
        # given a character with a hunter edge and perks
        character, hunter_edge, hunter_edge_perks = get_mock_hunter_edge_and_perks
        perk = hunter_edge_perks[0]

        # when we remove the perk from the edge
        service = CharacterEdgeService()
        await service.remove_perk_from_edge(perk=perk, edge=hunter_edge, character=character)

        # then we get a valid CharacterEdgeAndPerksDTO
        assert character.hunter_attributes.edges == [
            HunterAttributesEdgeModel(
                edge_id=hunter_edge.id,
                perk_ids=[x.id for x in hunter_edge_perks if x.id != perk.id],
            ),
        ]
        assert character.hunter_attributes.creed == "Creed"


class TestCharacterGiftsService:
    """Test character gifts service."""

    async def test_fetch_all_gifts_for_character(
        self,
        werewolf_character: Character,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify all gifts are fetched for character."""
        # given a character with werewolf attributes

        service = CharacterGiftsService()
        gifts = await service.fetch_all_gifts_for_character(werewolf_character)

        assert [x.id for x in gifts] == [werewolf_character.werewolf_attributes.gift_ids[0]]

    async def test_fetch_all_gifts_for_character_no_werewolf_attributes(
        self, character_factory: Callable[[dict[str, Any]], Character], debug: Callable[[Any], None]
    ) -> None:
        """Verify no gifts are fetched for character if no werewolf attributes."""
        # given a character without werewolf attributes
        character = await character_factory(character_class="MORTAL")
        service = CharacterGiftsService()
        gifts = await service.fetch_all_gifts_for_character(character)
        assert gifts == []

    async def test_fetch_gift_from_character_true(
        self,
        werewolf_character: Character,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify gift is fetched from character."""
        # given a character with werewolf attributes
        service = CharacterGiftsService()
        gift = await WerewolfGift.get(werewolf_character.werewolf_attributes.gift_ids[0])

        # when we check if the gift is on the character
        result = await service.fetch_gift_from_character(gift=gift, character=werewolf_character)

        # then the gift is returned
        assert result == gift

    async def test_fetch_gift_from_character_error(
        self,
        werewolf_character: Character,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify error is raised when gift is not on character."""
        # given a character with werewolf attributes
        service = CharacterGiftsService()
        gift = await WerewolfGift.find_one(
            WerewolfGift.is_archived == False,
            WerewolfGift.id != werewolf_character.werewolf_attributes.gift_ids[0],
        )

        # when we check if the gift is not on the character
        # then we get a validation error
        with pytest.raises(ValidationError):
            await service.fetch_gift_from_character(
                gift=gift, character=werewolf_character, raise_on_not_found=True
            )

    async def test_fetch_gift_from_character_no_error(
        self,
        werewolf_character: Character,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify no error is raised when gift is not on character and raise_on_not_found is False."""
        # given a character with werewolf attributes
        service = CharacterGiftsService()
        gift = await WerewolfGift.find_one(
            WerewolfGift.is_archived == False,
            WerewolfGift.id != werewolf_character.werewolf_attributes.gift_ids[0],
        )

        # when we check if the gift is not on the character

        result = await service.fetch_gift_from_character(
            gift=gift, character=werewolf_character, raise_on_not_found=False
        )

        # then we get None
        assert result is None

    async def test_fetch_gift_from_character_no_werewolf_attributes_error(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify error is raised when gift is not on character and raise_on_not_found is True."""
        # given a character without werewolf attributes
        character = await character_factory(character_class="MORTAL")
        service = CharacterGiftsService()
        gift = await WerewolfGift.find_one(WerewolfGift.is_archived == False)

        # when we check if the gift is on the character
        # then we get a validation error
        with pytest.raises(ValidationError):
            await service.fetch_gift_from_character(
                gift=gift, character=character, raise_on_not_found=True
            )

    async def test_fetch_gift_from_character_no_werewolf_attributes_no_error(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify no error is raised when gift is not on character and raise_on_not_found is False."""
        # given a character without werewolf attributes
        character = await character_factory(character_class="MORTAL")
        service = CharacterGiftsService()
        gift = await WerewolfGift.find_one(WerewolfGift.is_archived == False)

        # when we check if the gift is on the character
        result = await service.fetch_gift_from_character(
            gift=gift, character=character, raise_on_not_found=False
        )

        # then we get None
        assert result is None

    async def test_add_gift_to_character_new_character(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify gift is added to character."""
        # given a character without werewolf attributes
        character = await character_factory(character_class="MORTAL")
        gift = await WerewolfGift.find_one(WerewolfGift.is_archived == False)
        service = CharacterGiftsService()

        # when we add the gift to the character
        await service.add_gift_to_character(gift=gift, character=character)

        # then werewolf attributes are added to the character
        assert character.werewolf_attributes.gift_ids == [gift.id]
        assert character.werewolf_attributes.total_renown == 0
        assert character.werewolf_attributes.tribe_id == None

    async def test_add_gift_to_character_existing_character(
        self,
        werewolf_character: Character,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify gift is added to existing character."""
        # given a character with werewolf attributes
        service = CharacterGiftsService()
        original_gift_id = werewolf_character.werewolf_attributes.gift_ids[0]
        gift = await WerewolfGift.find_one(
            WerewolfGift.is_archived == False,
            WerewolfGift.id != original_gift_id,
        )

        # when we add the gift to the character
        await service.add_gift_to_character(gift=gift, character=werewolf_character)

        # then werewolf attributes are added to the character
        assert werewolf_character.werewolf_attributes.gift_ids == [original_gift_id, gift.id]
        assert werewolf_character.werewolf_attributes.total_renown == 10
        assert werewolf_character.werewolf_attributes.tribe_id is not None

    async def test_add_gift_to_character_gift_already_on_character(
        self,
        werewolf_character: Character,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify gift is not added to character if already on character."""
        # given a character with werewolf attributes
        service = CharacterGiftsService()
        original_gift_id = werewolf_character.werewolf_attributes.gift_ids[0]
        gift = await WerewolfGift.get(original_gift_id)
        await service.add_gift_to_character(gift=gift, character=werewolf_character)

        # then werewolf attributes are not changed
        assert werewolf_character.werewolf_attributes.gift_ids == [original_gift_id]
        assert werewolf_character.werewolf_attributes.total_renown == 10
        assert werewolf_character.werewolf_attributes.tribe_id is not None

    async def test_remove_gift_from_character_new_character(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify gift is removed from character."""
        # given a character without werewolf attributes
        character = await character_factory(character_class="MORTAL")
        gift = await WerewolfGift.find_one(WerewolfGift.is_archived == False)
        service = CharacterGiftsService()

        # when we remove the gift from the character
        await service.remove_gift_from_character(gift=gift, character=character)

        # then werewolf attributes are not changed
        assert character.werewolf_attributes is None or WerewolfAttributes()

    async def test_remove_gift_from_character_existing_character(
        self,
        werewolf_character: Character,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify gift is removed from existing character."""
        # given a character with werewolf attributes
        service = CharacterGiftsService()
        original_gift_id = werewolf_character.werewolf_attributes.gift_ids[0]
        gift = await WerewolfGift.get(original_gift_id)

        # when we remove the gift from the character
        await service.remove_gift_from_character(gift=gift, character=werewolf_character)

        # then werewolf attributes are updated
        assert werewolf_character.werewolf_attributes.gift_ids == []
        assert werewolf_character.werewolf_attributes.total_renown == 10
        assert werewolf_character.werewolf_attributes.tribe_id is not None


class TestCharacterRitesService:
    """Test character rites service."""

    async def test_fetch_all_rites_for_character(
        self,
        werewolf_character: Character,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify all rites are fetched for character."""
        # given a character with werewolf attributes

        service = CharacterRitesService()
        rites = await service.fetch_all_rites_for_character(werewolf_character)

        assert [x.id for x in rites] == [werewolf_character.werewolf_attributes.rite_ids[0]]

    async def test_fetch_all_rites_for_character_no_werewolf_attributes(
        self, character_factory: Callable[[dict[str, Any]], Character], debug: Callable[[Any], None]
    ) -> None:
        """Verify no rites are fetched for character if no werewolf attributes."""
        # given a character without werewolf attributes
        character = await character_factory(character_class="MORTAL")
        service = CharacterRitesService()
        rites = await service.fetch_all_rites_for_character(character)
        assert rites == []

    async def test_fetch_rite_from_character_true(
        self,
        werewolf_character: Character,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify rite is fetched from character."""
        # given a character with werewolf attributes
        service = CharacterRitesService()
        rite = await WerewolfRite.get(werewolf_character.werewolf_attributes.rite_ids[0])

        # when we check if the rite is on the character
        result = await service.fetch_rite_from_character(rite=rite, character=werewolf_character)

        # then the rite is returned
        assert result == rite

    async def test_fetch_rite_from_character_error(
        self,
        werewolf_character: Character,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify error is raised when rite is not on character."""
        # given a character with werewolf attributes
        service = CharacterRitesService()
        rite = await WerewolfRite.find_one(
            WerewolfRite.is_archived == False,
            WerewolfRite.id != werewolf_character.werewolf_attributes.rite_ids[0],
        )

        # when we check if the rite is not on the character
        # then we get a validation error
        with pytest.raises(ValidationError):
            await service.fetch_rite_from_character(
                rite=rite, character=werewolf_character, raise_on_not_found=True
            )

    async def test_fetch_rite_from_character_no_error(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify no error is raised when rite is not on character and raise_on_not_found is False."""
        # given a character without werewolf attributes
        character = await character_factory(character_class="MORTAL")
        service = CharacterRitesService()
        rite = await WerewolfRite.find_one(WerewolfRite.is_archived == False)

        # when we check if the rite is on the character
        result = await service.fetch_rite_from_character(
            rite=rite, character=character, raise_on_not_found=False
        )

        # then we get None
        assert result is None

    async def test_add_rite_to_character_new_character(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify rite is added to character."""
        # given a character without werewolf attributes
        character = await character_factory(character_class="MORTAL")
        rite = await WerewolfRite.find_one(WerewolfRite.is_archived == False)
        service = CharacterRitesService()

        # when we add the rite to the character
        await service.add_rite_to_character(rite=rite, character=character)

        # then werewolf attributes are added to the character
        assert character.werewolf_attributes.rite_ids == [rite.id]
        assert character.werewolf_attributes.total_renown == 0
        assert character.werewolf_attributes.tribe_id == None

    async def test_add_rite_to_character_existing_character(
        self,
        werewolf_character: Character,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify rite is added to existing character."""
        # given a character with werewolf attributes
        service = CharacterRitesService()
        original_rite_id = werewolf_character.werewolf_attributes.rite_ids[0]
        rite = await WerewolfRite.find_one(
            WerewolfRite.is_archived == False,
            WerewolfRite.id != original_rite_id,
        )

        # when we add the rite to the character
        await service.add_rite_to_character(rite=rite, character=werewolf_character)

        # then werewolf attributes are added to the character
        assert werewolf_character.werewolf_attributes.rite_ids == [original_rite_id, rite.id]
        assert werewolf_character.werewolf_attributes.total_renown == 10
        assert werewolf_character.werewolf_attributes.tribe_id is not None

    async def test_add_rite_to_character_rite_already_on_character(
        self,
        werewolf_character: Character,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify rite is not added to character if already on character."""
        # given a character with werewolf attributes
        service = CharacterRitesService()
        original_rite_id = werewolf_character.werewolf_attributes.rite_ids[0]
        rite = await WerewolfRite.get(original_rite_id)
        await service.add_rite_to_character(rite=rite, character=werewolf_character)

        # then werewolf attributes are not changed
        assert werewolf_character.werewolf_attributes.rite_ids == [original_rite_id]
        assert werewolf_character.werewolf_attributes.total_renown == 10
        assert werewolf_character.werewolf_attributes.tribe_id is not None

    async def test_remove_rite_from_character_new_character(
        self,
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify rite is removed from character."""
        # given a character without werewolf attributes
        character = await character_factory(character_class="MORTAL")
        rite = await WerewolfRite.find_one(WerewolfRite.is_archived == False)
        service = CharacterRitesService()

        # when we remove the rite from the character
        await service.remove_rite_from_character(rite=rite, character=character)

        # then werewolf attributes are not changed
        assert character.werewolf_attributes is None or WerewolfAttributes()

    async def test_remove_rite_from_character_existing_character(
        self,
        werewolf_character: Character,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify rite is removed from existing character."""
        # given a character with werewolf attributes
        service = CharacterRitesService()
        original_rite_id = werewolf_character.werewolf_attributes.rite_ids[0]
        rite = await WerewolfRite.get(original_rite_id)

        # when we remove the rite from the character
        await service.remove_rite_from_character(rite=rite, character=werewolf_character)

        # then werewolf attributes are updated
        assert werewolf_character.werewolf_attributes.rite_ids == []
        assert werewolf_character.werewolf_attributes.total_renown == 10
        assert werewolf_character.werewolf_attributes.tribe_id is not None
