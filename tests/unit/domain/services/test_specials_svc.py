"""Unit tests for character specials services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from vapi.db.models import (
    WerewolfAuspice,
    WerewolfGift,
    WerewolfRite,
    WerewolfTribe,
)
from vapi.db.models.character import WerewolfAttributes
from vapi.domain.services import (
    CharacterGiftsService,
    CharacterRitesService,
)
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.models import Character

pytestmark = pytest.mark.anyio


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
