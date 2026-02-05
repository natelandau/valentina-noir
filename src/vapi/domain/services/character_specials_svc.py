"""Character specials services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from beanie.operators import In

from vapi.db.models import HunterEdge, HunterEdgePerk, WerewolfGift, WerewolfRite
from vapi.db.models.character import HunterAttributes, HunterAttributesEdgeModel, WerewolfAttributes
from vapi.domain.controllers.character_specials import dto
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from beanie import PydanticObjectId

    from vapi.db.models import Character


class CharacterEdgeService:
    """Character edge service."""

    async def get_edge_and_perks_dto_by_id(
        self, edge_id: PydanticObjectId, character: Character, *, raise_on_not_found: bool = True
    ) -> dto.CharacterEdgeAndPerksDTO | None:
        """Get a character edge and its perks."""
        if not character.hunter_attributes:
            if raise_on_not_found:
                raise ValidationError(detail="Edge not found in character")
            return None

        hunter_attributes_edge = next(
            (edge for edge in character.hunter_attributes.edges if edge.edge_id == edge_id), None
        )
        if not hunter_attributes_edge:
            if raise_on_not_found:
                raise ValidationError(detail="Edge not found in character")
            return None

        db_edge = await HunterEdge.get(hunter_attributes_edge.edge_id)
        db_perks = await HunterEdgePerk.find(
            In(HunterEdgePerk.id, hunter_attributes_edge.perk_ids)
        ).to_list()

        return dto.CharacterEdgeAndPerksDTO(
            id=db_edge.id,
            name=db_edge.name,
            pool=db_edge.pool,
            system=db_edge.system,
            type=db_edge.type,
            description=db_edge.description,
            perks=[
                dto.CharacterPerkDTO(id=perk.id, name=perk.name, description=perk.description)
                for perk in db_perks
            ],
        )

    async def get_perk_dto_by_id(
        self,
        perk_id: PydanticObjectId,
        character: Character,
        *,
        raise_on_not_found: bool = True,
    ) -> dto.CharacterPerkDTO | None:
        """Get a perk dto by id."""
        if not character.hunter_attributes:
            if raise_on_not_found:
                raise ValidationError(detail="Edge not found in character")
            return None

        for edge in character.hunter_attributes.edges:
            found_perk_id = next((x for x in edge.perk_ids if x == perk_id), None)
            if found_perk_id:
                db_perk = await HunterEdgePerk.get(found_perk_id)
                return dto.CharacterPerkDTO(
                    id=db_perk.id, name=db_perk.name, description=db_perk.description
                )

        if raise_on_not_found:
            raise ValidationError(detail="Perk not found in character")
        return None

    async def add_edge_to_character(
        self,
        edge: HunterEdge,
        character: Character,
    ) -> dto.CharacterEdgeAndPerksDTO:
        """Add an edge to a character."""
        # For idempotency, check if the edge is already in the character
        existing_edge = await self.get_edge_and_perks_dto_by_id(
            edge_id=edge.id,
            character=character,
            raise_on_not_found=False,
        )
        if existing_edge:
            return existing_edge

        hunter_attributes = character.hunter_attributes or HunterAttributes()

        hunter_attributes.edges.append(HunterAttributesEdgeModel(edge_id=edge.id, perk_ids=[]))
        character.hunter_attributes = hunter_attributes
        await character.save()

        return await self.get_edge_and_perks_dto_by_id(edge_id=edge.id, character=character)

    async def add_perk_to_edge(
        self,
        perk: HunterEdgePerk,
        edge: HunterEdge,
        character: Character,
    ) -> dto.CharacterEdgeAndPerksDTO:
        """Add a perk to an edge.

        Args:
            perk: The perk to add to the edge.
            edge: The edge to add the perk to.
            character: The character to add the perk to.

        Returns:
            The edge and perks dto for the character.

        Raises:
            ValidationError: If the edge is not found in the character.
        """
        if perk.edge_id != edge.id:
            raise ValidationError(detail="Perk not found on edge")

        # if perk already exists, just return it
        existing_perk = await self.get_perk_dto_by_id(
            perk_id=perk.id,
            character=character,
            raise_on_not_found=False,
        )
        if existing_perk:
            return await self.get_edge_and_perks_dto_by_id(edge_id=edge.id, character=character)

        # ensure the edge is added to the character
        await self.add_edge_to_character(edge=edge, character=character)
        await character.sync()

        for character_edge in character.hunter_attributes.edges:
            if character_edge.edge_id == edge.id:
                character_edge.perk_ids.append(perk.id)
                break

        await character.save()
        return await self.get_edge_and_perks_dto_by_id(edge_id=edge.id, character=character)

    async def remove_edge_from_character(
        self,
        edge_id: PydanticObjectId,
        character: Character,
        *,
        raise_on_not_found: bool = True,
    ) -> None:
        """Remove an edge from a character."""
        existing_edge = await self.get_edge_and_perks_dto_by_id(
            edge_id=edge_id,
            character=character,
            raise_on_not_found=raise_on_not_found,
        )
        if existing_edge:
            character.hunter_attributes.edges = [
                x for x in character.hunter_attributes.edges if x.edge_id != edge_id
            ]

        await character.save()

    async def remove_perk_from_edge(
        self,
        perk: HunterEdgePerk,
        edge: HunterEdge,
        character: Character,
    ) -> None:
        """Remove a perk from an edge."""
        if perk.edge_id != edge.id:
            raise ValidationError(detail="Perk not found on edge")

        existing_perk = await self.get_perk_dto_by_id(
            perk_id=perk.id,
            character=character,
            raise_on_not_found=True,
        )

        if existing_perk:
            for character_edge in character.hunter_attributes.edges:
                if character_edge.edge_id == edge.id:
                    character_edge.perk_ids = [x for x in character_edge.perk_ids if x != perk.id]
                    break

        await character.save()


class CharacterGiftsService:
    """Character werewolf gifts service."""

    async def fetch_all_gifts_for_character(self, character: Character) -> list[WerewolfGift]:
        """Fetch all gifts for a character."""
        if not character.werewolf_attributes:
            return []

        return await WerewolfGift.find(
            WerewolfGift.is_archived == False,
            In(WerewolfGift.id, character.werewolf_attributes.gift_ids),
        ).to_list()

    async def fetch_gift_from_character(
        self,
        gift: WerewolfGift,
        character: Character,
        *,
        raise_on_not_found: bool = True,
    ) -> WerewolfGift | None:
        """Check if a gift is on a character."""
        if not character.werewolf_attributes:
            if raise_on_not_found:
                raise ValidationError(detail="Character has no werewolf attributes")
            return None

        if gift.id not in character.werewolf_attributes.gift_ids:
            if raise_on_not_found:
                raise ValidationError(detail="Gift not found on character")
            return None

        return gift

    async def add_gift_to_character(self, gift: WerewolfGift, character: Character) -> None:
        """Add a gift to a character."""
        if not character.werewolf_attributes:
            character.werewolf_attributes = WerewolfAttributes()

        if await self.fetch_gift_from_character(
            gift=gift, character=character, raise_on_not_found=False
        ):
            return

        character.werewolf_attributes.gift_ids.append(gift.id)
        await character.save()

    async def remove_gift_from_character(self, gift: WerewolfGift, character: Character) -> None:
        """Remove a gift from a character."""
        if not character.werewolf_attributes:
            return

        character.werewolf_attributes.gift_ids = [
            x for x in character.werewolf_attributes.gift_ids if x != gift.id
        ]
        await character.save()


class CharacterRitesService:
    """Character werewolf rites service."""

    async def fetch_all_rites_for_character(
        self,
        character: Character,
    ) -> list[WerewolfRite]:
        """Fetch all rites for a character."""
        if not character.werewolf_attributes:
            return []

        return await WerewolfRite.find(
            WerewolfRite.is_archived == False,
            In(WerewolfRite.id, character.werewolf_attributes.rite_ids),
        ).to_list()

    async def fetch_rite_from_character(
        self, rite: WerewolfRite, character: Character, *, raise_on_not_found: bool = True
    ) -> WerewolfRite | None:
        """Check if a rite is on a character."""
        if not character.werewolf_attributes:
            if raise_on_not_found:
                raise ValidationError(detail="Character has no werewolf attributes")
            return None

        if rite.id not in character.werewolf_attributes.rite_ids:
            if raise_on_not_found:
                raise ValidationError(detail="Rite not found on character")
            return None

        return rite

    async def add_rite_to_character(self, rite: WerewolfRite, character: Character) -> None:
        """Add a rite to a character."""
        if not character.werewolf_attributes:
            character.werewolf_attributes = WerewolfAttributes()

        if await self.fetch_rite_from_character(
            rite=rite, character=character, raise_on_not_found=False
        ):
            return

        character.werewolf_attributes.rite_ids.append(rite.id)
        await character.save()

    async def remove_rite_from_character(self, rite: WerewolfRite, character: Character) -> None:
        """Remove a rite from a character."""
        if not character.werewolf_attributes:
            return

        character.werewolf_attributes.rite_ids = [
            x for x in character.werewolf_attributes.rite_ids if x != rite.id
        ]
        await character.save()
