"""Test character."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

import pytest
from beanie import PydanticObjectId
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from vapi.constants import CharacterClass, CharacterStatus, CharacterType, GameVersion
from vapi.db.models import (
    Character,
    CharacterConcept,
    CharacterTrait,
    HunterEdge,
    HunterEdgePerk,
    Trait,
    VampireClan,
    WerewolfAuspice,
    WerewolfGift,
    WerewolfRite,
    WerewolfTribe,
)
from vapi.db.models.character import HunterAttributesEdgeModel
from vapi.domain.controllers.character.dto import CharacterTraitCreate, CreateCharacterDTO
from vapi.domain.urls import Characters as CharacterURL

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.models import User

pytestmark = pytest.mark.anyio

EXCLUDE_CHARACTER_FIELDS = {
    "archive_date",
    "is_archived",
    "is_temporary",
    "is_chargen",
    "chargen_session_id",
}


class TestCharacterController:
    """Test character controller."""

    async def test_list_characters_no_results(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        base_character: Character,
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can list characters."""
        await base_character.delete()

        response = await client.get(build_url(CharacterURL.LIST), headers=token_company_admin)
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == []

    async def test_list_characters_with_results(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        base_user: User,
        base_character: Character,
        token_company_admin: dict[str, str],
        user_factory: Callable[[dict[str, Any]], User],
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can list characters."""
        await base_character.delete()

        second_user = await user_factory()
        mortal_player_alive_baseuser = await character_factory(
            character_class="MORTAL", type="PLAYER", user_player_id=base_user.id
        )
        mage_storyteller_dead_seconduser = await character_factory(
            character_class="MAGE", type="STORYTELLER", status="DEAD", user_player_id=second_user.id
        )

        # Confirm listing all characters
        response = await client.get(build_url(CharacterURL.LIST), headers=token_company_admin)
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == [
            mortal_player_alive_baseuser.model_dump(
                mode="json",
                exclude=EXCLUDE_CHARACTER_FIELDS,
            ),
            mage_storyteller_dead_seconduser.model_dump(
                mode="json",
                exclude=EXCLUDE_CHARACTER_FIELDS,
            ),
        ]

        # Confirm listing characters by user_player_id
        response = await client.get(
            build_url(CharacterURL.LIST),
            headers=token_company_admin,
            params={"user_player_id": str(second_user.id)},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == [
            mage_storyteller_dead_seconduser.model_dump(
                mode="json",
                exclude=EXCLUDE_CHARACTER_FIELDS,
            ),
        ]

        # Confirm listing characters by user_creator_id and type
        response = await client.get(
            build_url(CharacterURL.LIST),
            headers=token_company_admin,
            params={"user_creator_id": str(base_user.id), "character_type": "STORYTELLER"},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == []

        # Confirm listing characters by character_class
        response = await client.get(
            build_url(CharacterURL.LIST),
            headers=token_company_admin,
            params={"character_class": "MAGE"},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == [
            mage_storyteller_dead_seconduser.model_dump(
                mode="json",
                exclude=EXCLUDE_CHARACTER_FIELDS,
            ),
        ]

        # Confirm listing characters by status
        response = await client.get(
            build_url(CharacterURL.LIST),
            headers=token_company_admin,
            params={"status": "DEAD"},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == [
            mage_storyteller_dead_seconduser.model_dump(
                mode="json",
                exclude=EXCLUDE_CHARACTER_FIELDS,
            ),
        ]

        # Confirm listing characters by character_type
        response = await client.get(
            build_url(CharacterURL.LIST),
            headers=token_company_admin,
            params={"character_type": "STORYTELLER"},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == [
            mage_storyteller_dead_seconduser.model_dump(
                mode="json",
                exclude=EXCLUDE_CHARACTER_FIELDS,
            ),
        ]

    async def test_get_character(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can get a character."""
        character = await character_factory()
        response = await client.get(
            build_url(CharacterURL.DETAIL, character_id=character.id), headers=token_company_admin
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == character.model_dump(
            mode="json",
            exclude=EXCLUDE_CHARACTER_FIELDS,
        )

        # Cleanup
        await character.delete()

    async def test_get_character_not_found(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we get a 404 when getting a character that doesn't exist."""
        response = await client.get(
            build_url(CharacterURL.DETAIL, character_id=PydanticObjectId()),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Character not found"

    async def test_patch_character(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can patch a character."""
        character = await character_factory()
        original_name_last = character.name_last
        response = await client.patch(
            build_url(CharacterURL.UPDATE, character_id=character.id),
            headers=token_company_admin,
            json={
                "name_first": "Updated name",
                "status": "DEAD",
            },
        )
        assert response.status_code == HTTP_200_OK
        updated_character = await Character.get(character.id)
        assert response.json() == updated_character.model_dump(
            mode="json",
            exclude=EXCLUDE_CHARACTER_FIELDS,
        )
        assert updated_character.name_first == "Updated name"
        assert updated_character.name_last == original_name_last
        assert updated_character.status == CharacterStatus.DEAD
        assert updated_character.date_killed is not None

        # Cleanup
        await updated_character.delete()

    async def test_delete_character(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can delete a character."""
        character = await character_factory()
        response = await client.delete(
            build_url(CharacterURL.DELETE, character_id=character.id), headers=token_company_admin
        )
        assert response.status_code == HTTP_204_NO_CONTENT

        response = await client.get(
            build_url(CharacterURL.DETAIL, character_id=character.id), headers=token_company_admin
        )
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Character not found"

        await character.sync()
        assert character.is_archived

        # Cleanup
        await character.delete()


class TestVampireAttributes:
    """Test vampire attributes."""

    async def test_create_character_vampire(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can create a vampire character."""
        vampire_clan = await VampireClan.find_one(
            VampireClan.is_archived == False, VampireClan.bane != None
        )

        response = await client.post(
            build_url(CharacterURL.CREATE),
            headers=token_company_admin,
            json={
                "name_first": "Test",
                "name_last": "Character",
                "name_nick": "The Pencil",
                "character_class": "VAMPIRE",
                "game_version": "V5",
                "type": "PLAYER",
                "vampire_attributes": {
                    "clan_id": str(vampire_clan.id),
                },
            },
        )
        # debug(response.json())
        assert response.status_code == HTTP_201_CREATED
        created_character_id = response.json()["id"]
        character = await Character.get(created_character_id)
        # debug(character)
        assert response.json() == character.model_dump(
            mode="json",
            exclude=EXCLUDE_CHARACTER_FIELDS,
        )
        assert character.vampire_attributes.clan_id == vampire_clan.id
        assert character.vampire_attributes.clan_name == vampire_clan.name
        assert character.vampire_attributes.bane in [vampire_clan.bane, vampire_clan.variant_bane]
        assert character.vampire_attributes.compulsion == vampire_clan.compulsion

        # Cleanup
        await character.delete()

    async def test_update_vampire_sire_and_generation(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can update a vampire character's sire and generation."""
        character = await character_factory(character_class="VAMPIRE")
        # debug(character)
        db_clan = await VampireClan.get(character.vampire_attributes.clan_id)
        original_clan_id = character.vampire_attributes.clan_id

        response = await client.patch(
            build_url(CharacterURL.UPDATE, character_id=character.id),
            headers=token_company_admin,
            json={
                "name_first": "Updated name",
                "vampire_attributes": {"sire": "Updated Sire", "generation": 22},
            },
        )
        assert response.status_code == HTTP_200_OK
        updated_character = await Character.get(character.id)
        await updated_character.sync()
        assert updated_character.name_first == "Updated name"
        assert updated_character.vampire_attributes.sire == "Updated Sire"
        assert updated_character.vampire_attributes.generation == 22
        assert updated_character.vampire_attributes.clan_id == original_clan_id
        assert updated_character.vampire_attributes.clan_name == db_clan.name
        assert updated_character.vampire_attributes.bane == db_clan.bane
        assert updated_character.vampire_attributes.compulsion == db_clan.compulsion
        assert response.json() == updated_character.model_dump(
            mode="json",
            exclude=EXCLUDE_CHARACTER_FIELDS,
        )

    async def test_update_character_vampire_clan(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can update a vampire character's clan."""
        # Given a vampire character and a new clan
        character = await character_factory(character_class="VAMPIRE")
        character.vampire_attributes.sire = "Updated Sire"
        await character.save()
        original_clan = await VampireClan.get(character.vampire_attributes.clan_id)
        assert original_clan is not None

        new_clan = await VampireClan.find_one(
            VampireClan.is_archived == False,
            VampireClan.id != original_clan.id,
            VampireClan.game_versions == GameVersion.V5,
        )

        # When we update the vampire character's clan
        response = await client.patch(
            build_url(CharacterURL.UPDATE, character_id=character.id),
            headers=token_company_admin,
            json={"vampire_attributes": {"clan_id": str(new_clan.id)}},
        )

        # Then verify the vampire character's clan was updated
        assert response.status_code == HTTP_200_OK
        updated_character = await Character.get(character.id)
        await updated_character.sync()
        assert updated_character.vampire_attributes.clan_id == new_clan.id
        assert updated_character.vampire_attributes.clan_name == new_clan.name
        assert updated_character.vampire_attributes.sire == "Updated Sire"
        assert updated_character.vampire_attributes.bane in [new_clan.bane, new_clan.variant_bane]
        assert updated_character.vampire_attributes.compulsion == new_clan.compulsion
        assert response.json() == updated_character.model_dump(
            mode="json", exclude=EXCLUDE_CHARACTER_FIELDS
        )

        # Cleanup
        await updated_character.delete()

    async def test_update_vampire_bane_and_compulsion(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can update a vampire character's bane and compulsion."""
        # Given a vampire character with a bane and compulsion
        character = await character_factory(character_class="VAMPIRE")
        original_clan = await VampireClan.get(character.vampire_attributes.clan_id)
        character.vampire_attributes.bane = original_clan.variant_bane
        character.vampire_attributes.compulsion = original_clan.compulsion
        character.vampire_attributes.clan_name = original_clan.name

        # When we update the vampire character's bane and compulsion
        response = await client.patch(
            build_url(CharacterURL.UPDATE, character_id=character.id),
            headers=token_company_admin,
            json={
                "vampire_attributes": {"bane": original_clan.variant_bane.model_dump()},
            },
        )

        # Then verify the vampire character's bane and compulsion were updated
        assert response.status_code == HTTP_200_OK
        updated_character = await Character.get(character.id)
        await updated_character.sync()
        assert updated_character.vampire_attributes.clan_id == original_clan.id
        assert updated_character.vampire_attributes.clan_name == original_clan.name
        assert updated_character.vampire_attributes.bane == original_clan.variant_bane
        assert updated_character.vampire_attributes.compulsion == original_clan.compulsion

        # Cleanup
        await updated_character.delete()


class TestWerewolfAttributes:
    """Test werewolf attributes."""

    async def test_create_character_werewolf(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can create a werewolf character."""
        werewolf_tribe = await WerewolfTribe.find_one({"is_archived": False})
        werewolf_auspice = await WerewolfAuspice.find_one({"is_archived": False})
        rites = await WerewolfRite.find().limit(3).to_list()
        gifts = await WerewolfGift.find().limit(3).to_list()
        response = await client.post(
            build_url(CharacterURL.CREATE),
            headers=token_company_admin,
            json={
                "name_first": "Test",
                "name_last": "Character",
                "character_class": "WEREWOLF",
                "game_version": "V5",
                "type": "PLAYER",
                "werewolf_attributes": {
                    "tribe_id": str(werewolf_tribe.id),
                    "auspice_id": str(werewolf_auspice.id),
                    "gift_ids": [str(gift.id) for gift in gifts],
                    "rite_ids": [str(rite.id) for rite in rites],
                },
            },
        )
        assert response.status_code == HTTP_201_CREATED
        created_character_id = response.json()["id"]
        character = await Character.get(created_character_id)
        assert response.json() == character.model_dump(
            mode="json", exclude=EXCLUDE_CHARACTER_FIELDS
        )
        assert character.werewolf_attributes.tribe_id == werewolf_tribe.id
        assert character.werewolf_attributes.tribe_name == werewolf_tribe.name
        assert character.werewolf_attributes.auspice_id == werewolf_auspice.id
        assert character.werewolf_attributes.auspice_name == werewolf_auspice.name
        assert len(character.werewolf_attributes.gift_ids) == 3
        assert len(character.werewolf_attributes.rite_ids) == 3

        # Cleanup
        await character.delete()

    async def test_update_character_werewolf(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can update a werewolf character."""
        new_tribe = await WerewolfTribe.find_one({"is_archived": False})

        character = await character_factory(character_class="WEREWOLF")
        original_auspice_id = character.werewolf_attributes.auspice_id
        # debug(character)

        response = await client.patch(
            build_url(CharacterURL.UPDATE, character_id=character.id),
            headers=token_company_admin,
            json={
                "name_first": "Updated name",
                "werewolf_attributes": {
                    "tribe_id": str(new_tribe.id),
                },
            },
        )
        # debug(response.json())
        assert response.status_code == HTTP_200_OK
        updated_character = await Character.get(character.id)
        await updated_character.sync()
        assert updated_character.name_first == "Updated name"
        assert updated_character.werewolf_attributes.tribe_id == new_tribe.id
        assert updated_character.werewolf_attributes.tribe_name == new_tribe.name
        assert updated_character.werewolf_attributes.auspice_id == original_auspice_id

        # assert updated_character.werewolf_attributes.auspice_name == new_auspice.name
        assert response.json() == updated_character.model_dump(
            mode="json", exclude=EXCLUDE_CHARACTER_FIELDS
        )

        # Cleanup
        await updated_character.delete()

    async def test_patch_werewolf_gifts_and_rites(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Test werewolf gifts and rites can be patched."""
        # Given a werewolf character with full werewolf attributes
        character = await character_factory(character_class="WEREWOLF")
        auspice = await WerewolfAuspice.find_one({"is_archived": False})
        tribe = await WerewolfTribe.find_one({"is_archived": False})
        rites = await WerewolfRite.find().to_list()
        gifts = await WerewolfGift.find().to_list()

        character.werewolf_attributes.tribe_id = tribe.id
        character.werewolf_attributes.auspice_id = auspice.id
        character.werewolf_attributes.tribe_name = tribe.name
        character.werewolf_attributes.auspice_name = auspice.name
        character.werewolf_attributes.rite_ids = [random.choice(rites).id for _ in range(3)]
        character.werewolf_attributes.gift_ids = [random.choice(gifts).id for _ in range(3)]
        await character.save()

        # When we patch the character with a new gift
        new_gift = random.choice(gifts)
        response = await client.patch(
            build_url(CharacterURL.UPDATE, character_id=character.id),
            headers=token_company_admin,
            json={
                "werewolf_attributes": {"gift_ids": [str(new_gift.id)]},
            },
        )
        # debug(response.json())

        # Then verify the character was updated successfully
        updated_character = await Character.get(character.id)
        await updated_character.sync()
        assert updated_character.werewolf_attributes.gift_ids == [new_gift.id]
        assert (
            updated_character.werewolf_attributes.rite_ids == character.werewolf_attributes.rite_ids
        )
        assert updated_character.werewolf_attributes.auspice_name == auspice.name
        assert updated_character.werewolf_attributes.tribe_name == tribe.name
        assert response.json() == updated_character.model_dump(
            mode="json", exclude=EXCLUDE_CHARACTER_FIELDS
        )

    async def test_patch_werewolf_tribe(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Test werewolf tribe and auspice can be patched."""
        # Given a werewolf character with full werewolf attributes
        character = await character_factory(character_class="WEREWOLF")
        auspice = await WerewolfAuspice.find_one({"is_archived": False})
        tribe = await WerewolfTribe.find_one({"is_archived": False})
        rites = await WerewolfRite.find().to_list()
        gifts = await WerewolfGift.find().to_list()
        character.werewolf_attributes.tribe_id = tribe.id
        character.werewolf_attributes.auspice_id = auspice.id
        character.werewolf_attributes.tribe_name = tribe.name
        character.werewolf_attributes.auspice_name = auspice.name
        character.werewolf_attributes.rite_ids = [random.choice(rites).id for _ in range(3)]
        character.werewolf_attributes.gift_ids = [random.choice(gifts).id for _ in range(3)]
        await character.save()

        # When we patch the character with a new tribe
        new_tribe = await WerewolfTribe.find_one(
            WerewolfTribe.is_archived == False, WerewolfTribe.id != tribe.id
        )
        response = await client.patch(
            build_url(CharacterURL.UPDATE, character_id=character.id),
            headers=token_company_admin,
            json={
                "werewolf_attributes": {"tribe_id": str(new_tribe.id)},
            },
        )
        # debug(response.json())

        # Then verify the character was updated successfully
        updated_character = await Character.get(character.id)
        await updated_character.sync()
        assert updated_character.werewolf_attributes.tribe_id == new_tribe.id
        assert updated_character.werewolf_attributes.tribe_name == new_tribe.name
        assert updated_character.werewolf_attributes.auspice_id == auspice.id
        assert updated_character.werewolf_attributes.auspice_name == auspice.name
        assert (
            updated_character.werewolf_attributes.rite_ids == character.werewolf_attributes.rite_ids
        )
        assert (
            updated_character.werewolf_attributes.gift_ids == character.werewolf_attributes.gift_ids
        )
        assert response.json() == updated_character.model_dump(
            mode="json", exclude=EXCLUDE_CHARACTER_FIELDS
        )


class TestHunterAttributes:
    """Test hunter attributes."""

    async def test_create_character_hunter(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can create a hunter character."""
        # Given hunter edges and perks
        hunter_edge = await HunterEdge.find_one(HunterEdge.is_archived == False)
        hunter_edge_perks = await HunterEdgePerk.find(
            HunterEdgePerk.is_archived == False, HunterEdgePerk.edge_id == hunter_edge.id
        ).to_list()

        # When we create a character with hunter attributes
        response = await client.post(
            build_url(CharacterURL.CREATE),
            headers=token_company_admin,
            json={
                "name_first": "Test",
                "name_last": "Hunter",
                "character_class": "HUNTER",
                "game_version": "V5",
                "type": "PLAYER",
                "hunter_attributes": {
                    "creed": "Test Creed",
                    "edges": [
                        {
                            "edge_id": str(hunter_edge.id),
                            "perk_ids": [
                                str(hunter_edge_perk.id) for hunter_edge_perk in hunter_edge_perks
                            ],
                        }
                    ],
                },
            },
        )
        # debug(response.json()["hunter_attributes"])

        # Then verify the character was created successfully
        assert response.status_code == HTTP_201_CREATED
        character = await Character.get(response.json()["id"])
        assert response.json() == character.model_dump(
            mode="json", exclude=EXCLUDE_CHARACTER_FIELDS
        )
        assert character.hunter_attributes.creed == "Test Creed"
        assert character.hunter_attributes.edges == [
            HunterAttributesEdgeModel(
                edge_id=hunter_edge.id,
                perk_ids=[hunter_edge_perk.id for hunter_edge_perk in hunter_edge_perks],
            )
        ]

        # Cleanup
        await character.delete()

    async def test_patch_hunter(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, Any]], Character],
        debug: Callable[[Any], None],
    ) -> None:
        """Test patch hunter attributes."""
        # Given a character
        character = await character_factory(character_class="HUNTER")
        hunter_edge = await HunterEdge.find_one(HunterEdge.is_archived == False)
        hunter_edge_perks = await HunterEdgePerk.find(
            HunterEdgePerk.is_archived == False, HunterEdgePerk.edge_id == hunter_edge.id
        ).to_list()
        character.hunter_attributes.edges = [
            HunterAttributesEdgeModel(
                edge_id=hunter_edge.id,
                perk_ids=[hunter_edge_perk.id for hunter_edge_perk in hunter_edge_perks],
            )
        ]
        character.hunter_attributes.creed = "Test Creed"
        await character.save()
        # debug(character)

        # When we patch the character with a new creed
        new_creed = "New Creed"
        response = await client.patch(
            build_url(CharacterURL.UPDATE, character_id=character.id),
            headers=token_company_admin,
            json={
                "hunter_attributes": {"creed": new_creed},
            },
        )
        # debug(response.json()["hunter_attributes"])

        # Then verify the character was updated successfully
        updated_character = await Character.get(character.id)
        await updated_character.sync()
        assert updated_character.hunter_attributes.creed == new_creed
        assert updated_character.hunter_attributes.edges == character.hunter_attributes.edges
        assert response.json() == updated_character.model_dump(
            mode="json", exclude=EXCLUDE_CHARACTER_FIELDS
        )

        # Cleanup
        await updated_character.delete()


class TestCharacterCreate:
    """Test character create endpoints."""

    async def test_create_character(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        all_traits_in_section: Callable[[str], list[Trait]],
        debug: Callable[[Any], None],
    ) -> None:
        """Test create character endpoint."""
        # given valid create character data
        attribute_traits = await all_traits_in_section("Abilities")
        traits = [
            CharacterTraitCreate(trait_id=str(trait.id), value=1) for trait in attribute_traits
        ]
        create_character_data = CreateCharacterDTO(
            name_first="Test",
            name_last="Character",
            character_class=CharacterClass.MORTAL,
            game_version=GameVersion.V5,
            type=CharacterType.PLAYER,
            traits=traits,
        )

        # When we create a character with traits
        response = await client.post(
            build_url(CharacterURL.CREATE),
            headers=token_company_admin,
            json=create_character_data.model_dump(mode="json"),
        )
        # debug(response.json())

        # Then verify the character was created successfully
        assert response.status_code == HTTP_201_CREATED
        created_character_id = response.json()["id"]

        character = await Character.get(created_character_id)

        assert response.json() == character.model_dump(
            mode="json",
            exclude={
                "archive_date",
                "is_archived",
                "is_temporary",
                "is_chargen",
                "chargen_session_id",
            },
        )
        # debug(character)

        assert len(character.character_trait_ids) == len(traits)
        character_traits = [
            await CharacterTrait.get(x, fetch_links=True) for x in character.character_trait_ids
        ]
        character_trait_ids = {str(x.trait.id) for x in character_traits}
        trait_ids = {str(x.trait_id) for x in traits}

        assert character_trait_ids == trait_ids

        # Cleanup
        await character.delete()

    @pytest.mark.parametrize(
        "json_data",
        [
            ({"name_first": "a"}),
            ({"name_last": "b"}),
            ({"game_version": "INVALID"}),
            ({"type": "INVALID"}),
            ({"biography": "a"}),
            ({"demeanor": "a"}),
            ({"nature": "a"}),
            ({"name_nick": "a"}),
            ({"character_class": "INVALID"}),
            ({"concept_id": "INVALID"}),
            ({"user_player_id": "INVALID"}),
        ],
    )
    async def test_create_character_invalid_parameters(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        json_data: dict[str, Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we get a 400 when creating a character with invalid parameters."""
        correct_json_data = {
            "name_first": "Test",
            "name_last": "Character",
            "character_class": "MORTAL",
            "game_version": "V5",
            "type": "PLAYER",
            "biography": "Test biography",
            "demeanor": "Test demeanor",
            "nature": "Test nature",
        }

        base_json_data = {**correct_json_data, **json_data}

        response = await client.post(
            build_url(CharacterURL.CREATE),
            headers=token_company_admin,
            json=base_json_data,
        )
        # debug(response.json())
        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_invalid_user_player(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        base_user: User,
        token_company_admin: dict[str, str],
        debug: Callable[[Any], None],
        user_factory: Callable[[dict[str, Any]], User],
    ) -> None:
        """Test no invalid user player."""
        archived_user = await user_factory(is_archived=True)

        # debug(archived_user)

        response = await client.post(
            build_url(CharacterURL.CREATE, user_id=archived_user.id),
            headers=token_company_admin,
            json={
                "name_first": "Test invalid user player",
                "name_last": "Character",
                "character_class": "MORTAL",
                "game_version": "V5",
                "type": "PLAYER",
            },
        )
        # debug(response.json())
        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_create_character_with_everything(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        user_factory: Callable[[dict[str, Any]], User],
        all_traits_in_section: Callable[[str], list[Trait]],
        debug: Callable[[Any], None],
    ) -> None:
        """Test create character endpoint with everything."""
        user_player = await user_factory()
        vampire_clan = await VampireClan.find_one(
            VampireClan.is_archived == False, VampireClan.game_versions == "V5"
        )
        concept = await CharacterConcept.find_one(CharacterConcept.is_archived == False)
        attribute_traits = await all_traits_in_section("Attributes")
        traits = [
            CharacterTraitCreate(trait_id=str(trait.id), value=0) for trait in attribute_traits
        ]

        create_character_data = CreateCharacterDTO(
            name_first="Test",
            name_last="Character",
            name_nick="The Pencil",
            age=20,
            biography="Test biography",
            demeanor="Test demeanor",
            nature="Test nature",
            character_class=CharacterClass.VAMPIRE,
            game_version=GameVersion.V5,
            type=CharacterType.PLAYER,
            traits=traits,
            vampire_attributes={
                "clan_id": str(vampire_clan.id),
                "sire": "Test Sire",
                "generation": 1,
            },
            concept_id=str(concept.id),
            user_player_id=str(user_player.id),
        )

        # When we create a character with everything
        response = await client.post(
            build_url(CharacterURL.CREATE),
            headers=token_company_admin,
            json=create_character_data.model_dump(mode="json"),
        )
        # debug(response.json())

        # Then verify the character was created successfully
        assert response.status_code == HTTP_201_CREATED

        created_character_id = response.json()["id"]
        character = await Character.get(created_character_id)

        assert response.json() == character.model_dump(
            mode="json",
            exclude={
                "archive_date",
                "is_archived",
                "is_temporary",
                "is_chargen",
                "chargen_session_id",
            },
        )
        assert character.name_first == "Test"
        assert character.name_last == "Character"
        assert character.name_nick == "The Pencil"
        assert character.age == 20
        assert character.biography == "Test biography"
        assert character.demeanor == "Test demeanor"
        assert character.nature == "Test nature"
        assert character.character_class == CharacterClass.VAMPIRE
        assert character.vampire_attributes.clan_id == vampire_clan.id
        assert character.vampire_attributes.clan_name == vampire_clan.name
        assert character.vampire_attributes.bane in [vampire_clan.bane, vampire_clan.variant_bane]
        assert character.vampire_attributes.compulsion == vampire_clan.compulsion
        assert character.vampire_attributes.sire == "Test Sire"
        assert character.vampire_attributes.generation == 1
        assert character.concept_id == concept.id
        assert character.user_player_id == user_player.id
        # Add one to the size of the list b/c willpower is created
        assert len(character.character_trait_ids) == len(traits) + 1
        assert character.specialties == concept.specialties

        # Cleanup
        await character.delete()
