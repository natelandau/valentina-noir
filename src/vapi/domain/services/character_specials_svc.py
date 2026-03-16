"""Character specials services."""

from __future__ import annotations

from typing import TYPE_CHECKING

from beanie.operators import In

from vapi.db.models import WerewolfGift, WerewolfRite
from vapi.db.models.character import WerewolfAttributes
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from vapi.db.models import Character


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
