"""Test character specials controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
)

from vapi.db.models import (
    Character,
    WerewolfAuspice,
    WerewolfGift,
    WerewolfRite,
    WerewolfTribe,
)
from vapi.db.models.character import WerewolfAttributes
from vapi.domain.urls import Characters

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient


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


class TestWerewolfSpecialsController:
    """Test werewolf specials controller."""

    async def test_list_werewolf_gifts(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test list werewolf gifts."""
        gift = await WerewolfGift.get(werewolf_character.werewolf_attributes.gift_ids[0])
        response = await client.get(
            build_url(Characters.GIFTS, character_id=werewolf_character.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == 1
        assert response.json()["items"] == [
            gift.model_dump(mode="json", exclude={"is_archived", "archive_date"})
        ]
        assert response.json()["limit"] == 10
        assert response.json()["offset"] == 0

    async def test_get_werewolf_gift(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test get werewolf gift."""
        gift = await WerewolfGift.get(werewolf_character.werewolf_attributes.gift_ids[0])
        response = await client.get(
            build_url(
                Characters.GIFT_DETAIL, character_id=werewolf_character.id, werewolf_gift_id=gift.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == gift.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )

    async def test_add_werewolf_gift(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test add werewolf gift."""
        gift = await WerewolfGift.find_one(
            WerewolfGift.is_archived == False,
            WerewolfGift.id != werewolf_character.werewolf_attributes.gift_ids[0],
        )
        response = await client.post(
            build_url(
                Characters.GIFT_ADD, character_id=werewolf_character.id, werewolf_gift_id=gift.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_201_CREATED
        assert response.json() == gift.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )
        await werewolf_character.sync()
        assert werewolf_character.werewolf_attributes.gift_ids == [
            werewolf_character.werewolf_attributes.gift_ids[0],
            gift.id,
        ]
        assert werewolf_character.werewolf_attributes.total_renown == 10
        assert werewolf_character.werewolf_attributes.tribe_id is not None

    async def test_remove_werewolf_gift(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test remove werewolf gift."""
        gift = await WerewolfGift.get(werewolf_character.werewolf_attributes.gift_ids[0])
        response = await client.delete(
            build_url(
                Characters.GIFT_REMOVE, character_id=werewolf_character.id, werewolf_gift_id=gift.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_204_NO_CONTENT
        await werewolf_character.sync()
        assert werewolf_character.werewolf_attributes.gift_ids == []
        assert werewolf_character.werewolf_attributes.total_renown == 10
        assert werewolf_character.werewolf_attributes.tribe_id is not None


class TestWerewolfRitesController:
    """Test werewolf rites controller."""

    async def test_list_werewolf_rites(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test list werewolf rites."""
        rite = await WerewolfRite.get(werewolf_character.werewolf_attributes.rite_ids[0])
        response = await client.get(
            build_url(Characters.RITES, character_id=werewolf_character.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["total"] == 1
        assert response.json()["items"] == [
            rite.model_dump(mode="json", exclude={"is_archived", "archive_date"})
        ]
        assert response.json()["limit"] == 10
        assert response.json()["offset"] == 0

    async def test_get_werewolf_rite(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test get werewolf rite."""
        rite = await WerewolfRite.get(werewolf_character.werewolf_attributes.rite_ids[0])
        response = await client.get(
            build_url(
                Characters.RITE_DETAIL, character_id=werewolf_character.id, werewolf_rite_id=rite.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == rite.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )

    async def test_add_werewolf_rite(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test add werewolf rite."""
        rite = await WerewolfRite.find_one(
            WerewolfRite.is_archived == False,
            WerewolfRite.id != werewolf_character.werewolf_attributes.rite_ids[0],
        )
        response = await client.post(
            build_url(
                Characters.RITE_ADD, character_id=werewolf_character.id, werewolf_rite_id=rite.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_201_CREATED
        assert response.json() == rite.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )
        await werewolf_character.sync()
        assert werewolf_character.werewolf_attributes.rite_ids == [
            werewolf_character.werewolf_attributes.rite_ids[0],
            rite.id,
        ]
        assert werewolf_character.werewolf_attributes.total_renown == 10

    async def test_remove_werewolf_rite(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        werewolf_character: Character,
    ) -> None:
        """Test remove werewolf rite."""
        rite = await WerewolfRite.get(werewolf_character.werewolf_attributes.rite_ids[0])
        response = await client.delete(
            build_url(
                Characters.RITE_REMOVE, character_id=werewolf_character.id, werewolf_rite_id=rite.id
            ),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_204_NO_CONTENT
        await werewolf_character.sync()
        assert werewolf_character.werewolf_attributes.rite_ids == []
        assert werewolf_character.werewolf_attributes.total_renown == 10
        assert werewolf_character.werewolf_attributes.tribe_id is not None
