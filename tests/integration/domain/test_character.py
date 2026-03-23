"""Test character."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from beanie import PydanticObjectId
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from vapi.constants import CharacterClass, CharacterStatus, CharacterType, GameVersion, UserRole
from vapi.db.models import (
    Character,
    CharacterConcept,
    CharacterTrait,
    Trait,
    TraitCategory,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)
from vapi.domain.controllers.character.dto import CharacterTraitCreate, CreateCharacterDTO
from vapi.domain.urls import Characters as CharacterURL

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.models import Campaign, Company, User

pytestmark = pytest.mark.anyio

EXCLUDE_CHARACTER_FIELDS = {
    "archive_date",
    "is_archived",
    "is_chargen",
}


@pytest.fixture
async def get_company_user_and_campaign(
    company_factory: Callable[[dict[str, ...]], Company],
    user_factory: Callable[[dict[str, ...]], User],
    campaign_factory: Callable[[dict[str, ...]], Campaign],
) -> tuple[Company, User]:
    """Get a company and user."""
    company = await company_factory()
    user = await user_factory(company_id=company.id, role=UserRole.ADMIN)
    campaign = await campaign_factory(company_id=company.id)

    yield company, user, campaign

    await user.delete()
    await company.delete()
    await campaign.delete()


class TestCharacterList:
    """Test character list endpoints."""

    async def test_list_characters_no_results(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        get_company_user_and_campaign: tuple[Company, User, Campaign],
        token_global_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify we can list characters."""
        company, user, campaign = get_company_user_and_campaign

        response = await client.get(
            build_url(
                CharacterURL.LIST, company_id=company.id, user_id=user.id, campaign_id=campaign.id
            ),
            headers=token_global_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == []

    async def test_list_characters_with_results_no_filters(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        get_company_user_and_campaign: tuple[Company, User, Campaign],
        character_factory: Callable[[dict[str, ...]], Character],
        token_global_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify we can list characters."""
        # Given a company, user, campaign, and characters
        company, user, campaign = get_company_user_and_campaign
        second_user_id = PydanticObjectId()
        character1 = await character_factory(
            company_id=company.id, user_player_id=user.id, campaign_id=campaign.id
        )
        character_dead = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            status=CharacterStatus.DEAD,
        )
        character_storyteller = await character_factory(
            company_id=company.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            type=CharacterType.STORYTELLER,
        )
        character_different_user = await character_factory(
            company_id=company.id,
            user_creator_id=user.id,
            user_player_id=second_user_id,
            campaign_id=campaign.id,
        )
        character_different_campaign = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=PydanticObjectId(),
        )
        character_archived = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            is_archived=True,
        )
        character_temporary = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            is_temporary=True,
        )

        # When we list characters
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=company.id,
                user_id=user.id,
                campaign_id=campaign.id,
            ),
            headers=token_global_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == [
            character1.model_dump(mode="json", exclude=EXCLUDE_CHARACTER_FIELDS),
            character_dead.model_dump(mode="json", exclude=EXCLUDE_CHARACTER_FIELDS),
            character_storyteller.model_dump(mode="json", exclude=EXCLUDE_CHARACTER_FIELDS),
            character_different_user.model_dump(mode="json", exclude=EXCLUDE_CHARACTER_FIELDS),
        ]

        # Cleanup
        await character1.delete()
        await character_dead.delete()
        await character_storyteller.delete()
        await character_different_user.delete()
        await character_different_campaign.delete()
        await character_archived.delete()
        await character_temporary.delete()

    async def test_list_characters_with_results_specify_user_player_id(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        get_company_user_and_campaign: tuple[Company, User, Campaign],
        character_factory: Callable[[dict[str, ...]], Character],
        token_global_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify we can list characters."""
        # Given a company, user, campaign, and characters
        company, user, campaign = get_company_user_and_campaign
        second_user_id = PydanticObjectId()
        character1 = await character_factory(
            company_id=company.id, user_player_id=user.id, campaign_id=campaign.id
        )
        character_dead = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            status=CharacterStatus.DEAD,
        )
        character_storyteller = await character_factory(
            company_id=company.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            type=CharacterType.STORYTELLER,
        )
        character_different_user = await character_factory(
            company_id=company.id,
            user_player_id=second_user_id,
            campaign_id=campaign.id,
        )
        character_different_campaign = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=PydanticObjectId(),
        )
        character_archived = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            is_archived=True,
        )
        character_temporary = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            is_temporary=True,
        )

        # When we list characters
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=company.id,
                user_id=user.id,
                campaign_id=campaign.id,
            ),
            headers=token_global_admin,
            params={"user_player_id": str(second_user_id)},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == [
            character_different_user.model_dump(mode="json", exclude=EXCLUDE_CHARACTER_FIELDS)
        ]

        # Cleanup
        await character1.delete()
        await character_dead.delete()
        await character_storyteller.delete()
        await character_different_user.delete()
        await character_different_campaign.delete()
        await character_archived.delete()
        await character_temporary.delete()

    async def test_list_characters_with_results_specify_user_creator_id(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        get_company_user_and_campaign: tuple[Company, User, Campaign],
        character_factory: Callable[[dict[str, ...]], Character],
        token_global_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify we can list characters."""
        # Given a company, user, campaign, and characters
        company, user, campaign = get_company_user_and_campaign
        second_user_id = PydanticObjectId()
        character1 = await character_factory(
            company_id=company.id, user_player_id=user.id, campaign_id=campaign.id
        )
        character_dead = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            status=CharacterStatus.DEAD,
        )
        character_storyteller = await character_factory(
            company_id=company.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            type=CharacterType.STORYTELLER,
        )
        character_different_user = await character_factory(
            company_id=company.id,
            user_creator_id=second_user_id,
            user_player_id=second_user_id,
            campaign_id=campaign.id,
        )
        character_different_campaign = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=PydanticObjectId(),
        )
        character_archived = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            is_archived=True,
        )
        character_temporary = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            is_temporary=True,
        )

        # When we list characters
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=company.id,
                user_id=user.id,
                campaign_id=campaign.id,
            ),
            headers=token_global_admin,
            params={"user_creator_id": str(second_user_id)},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == [
            character_different_user.model_dump(mode="json", exclude=EXCLUDE_CHARACTER_FIELDS)
        ]

        # Cleanup
        await character1.delete()
        await character_dead.delete()
        await character_storyteller.delete()
        await character_different_user.delete()
        await character_different_campaign.delete()
        await character_archived.delete()
        await character_temporary.delete()

    async def test_list_characters_with_results_specify_user_type(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        get_company_user_and_campaign: tuple[Company, User, Campaign],
        character_factory: Callable[[dict[str, ...]], Character],
        token_global_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify we can list characters."""
        # Given a company, user, campaign, and characters
        company, user, campaign = get_company_user_and_campaign
        second_user_id = PydanticObjectId()
        character1 = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.VAMPIRE,
        )
        character_dead = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            status=CharacterStatus.DEAD,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )
        character_storyteller = await character_factory(
            company_id=company.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            type=CharacterType.STORYTELLER,
            character_class=CharacterClass.VAMPIRE,
        )
        character_different_user = await character_factory(
            company_id=company.id,
            user_creator_id=second_user_id,
            user_player_id=second_user_id,
            campaign_id=campaign.id,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )
        character_different_campaign = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=PydanticObjectId(),
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )
        character_archived = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            is_archived=True,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )
        character_temporary = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            is_temporary=True,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )

        # When we list characters
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=company.id,
                user_id=user.id,
                campaign_id=campaign.id,
            ),
            headers=token_global_admin,
            params={"character_type": CharacterType.STORYTELLER.value},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == [
            character_storyteller.model_dump(mode="json", exclude=EXCLUDE_CHARACTER_FIELDS)
        ]

        # Cleanup
        await character1.delete()
        await character_dead.delete()
        await character_storyteller.delete()
        await character_different_user.delete()
        await character_different_campaign.delete()
        await character_archived.delete()
        await character_temporary.delete()

    async def test_list_characters_with_results_specify_character_class(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        get_company_user_and_campaign: tuple[Company, User, Campaign],
        character_factory: Callable[[dict[str, ...]], Character],
        token_global_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify we can list characters."""
        # Given a company, user, campaign, and characters
        company, user, campaign = get_company_user_and_campaign
        second_user_id = PydanticObjectId()
        character1 = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.VAMPIRE,
        )
        character_dead = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            status=CharacterStatus.DEAD,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )
        character_storyteller = await character_factory(
            company_id=company.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            type=CharacterType.STORYTELLER,
            character_class=CharacterClass.VAMPIRE,
        )
        character_different_user = await character_factory(
            company_id=company.id,
            user_creator_id=second_user_id,
            user_player_id=second_user_id,
            campaign_id=campaign.id,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )
        character_different_campaign = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=PydanticObjectId(),
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )
        character_archived = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            is_archived=True,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )
        character_temporary = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            is_temporary=True,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )

        # When we list characters
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=company.id,
                user_id=user.id,
                campaign_id=campaign.id,
            ),
            headers=token_global_admin,
            params={"character_class": CharacterClass.VAMPIRE.value},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == [
            character1.model_dump(mode="json", exclude=EXCLUDE_CHARACTER_FIELDS),
            character_storyteller.model_dump(mode="json", exclude=EXCLUDE_CHARACTER_FIELDS),
        ]

        # Cleanup
        await character1.delete()
        await character_dead.delete()
        await character_storyteller.delete()
        await character_different_user.delete()
        await character_different_campaign.delete()
        await character_archived.delete()
        await character_temporary.delete()

    async def test_list_characters_with_results_specify_character_status(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        get_company_user_and_campaign: tuple[Company, User, Campaign],
        character_factory: Callable[[dict[str, ...]], Character],
        token_global_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify we can list characters."""
        # Given a company, user, campaign, and characters
        company, user, campaign = get_company_user_and_campaign
        second_user_id = PydanticObjectId()
        character1 = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.VAMPIRE,
        )
        character_dead = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            status=CharacterStatus.DEAD,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )
        character_storyteller = await character_factory(
            company_id=company.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            type=CharacterType.STORYTELLER,
            character_class=CharacterClass.VAMPIRE,
        )
        character_different_user = await character_factory(
            company_id=company.id,
            user_creator_id=second_user_id,
            user_player_id=second_user_id,
            campaign_id=campaign.id,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )
        character_different_campaign = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=PydanticObjectId(),
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )
        character_archived = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            is_archived=True,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )
        character_temporary = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            is_temporary=True,
            type=CharacterType.PLAYER,
            character_class=CharacterClass.MORTAL,
        )

        # When we list characters
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=company.id,
                user_id=user.id,
                campaign_id=campaign.id,
            ),
            headers=token_global_admin,
            params={"status": CharacterStatus.DEAD.value},
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == [
            character_dead.model_dump(mode="json", exclude=EXCLUDE_CHARACTER_FIELDS),
        ]

        # Cleanup
        await character1.delete()
        await character_dead.delete()
        await character_storyteller.delete()
        await character_different_user.delete()
        await character_different_campaign.delete()
        await character_archived.delete()
        await character_temporary.delete()

    async def test_list_characters_with_results_specify_show_temporary(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        get_company_user_and_campaign: tuple[Company, User, Campaign],
        character_factory: Callable[[dict[str, ...]], Character],
        token_global_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify we can list characters."""
        # Given a company, user, campaign, and characters
        company, user, campaign = get_company_user_and_campaign
        second_user_id = PydanticObjectId()
        character1 = await character_factory(
            company_id=company.id, user_player_id=user.id, campaign_id=campaign.id
        )
        character_dead = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            status=CharacterStatus.DEAD,
        )
        character_storyteller = await character_factory(
            company_id=company.id,
            user_creator_id=user.id,
            campaign_id=campaign.id,
            type=CharacterType.STORYTELLER,
        )
        character_different_user = await character_factory(
            company_id=company.id,
            user_creator_id=user.id,
            user_player_id=second_user_id,
            campaign_id=campaign.id,
        )
        character_different_campaign = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=PydanticObjectId(),
        )
        character_archived = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            is_archived=True,
        )
        character_temporary = await character_factory(
            company_id=company.id,
            user_player_id=user.id,
            campaign_id=campaign.id,
            is_temporary=True,
        )

        # When we list characters
        response = await client.get(
            build_url(
                CharacterURL.LIST,
                company_id=company.id,
                user_id=user.id,
                campaign_id=campaign.id,
            ),
            params={"is_temporary": True},
            headers=token_global_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == [
            character_temporary.model_dump(mode="json", exclude=EXCLUDE_CHARACTER_FIELDS)
        ]

        # Cleanup
        await character1.delete()
        await character_dead.delete()
        await character_storyteller.delete()
        await character_different_user.delete()
        await character_different_campaign.delete()
        await character_archived.delete()
        await character_temporary.delete()


class TestCharacterController:
    """Test character controller."""

    async def test_get_character(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, ...]], Character],
        debug: Callable[[...], None],
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
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
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
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, ...]], Character],
        debug: Callable[[...], None],
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
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, ...]], Character],
        debug: Callable[[...], None],
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


@pytest.mark.clean_db
class TestVampireAttributes:
    """Test vampire attributes."""

    async def test_create_character_vampire(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
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
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, ...]], Character],
        debug: Callable[[...], None],
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
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, ...]], Character],
        debug: Callable[[...], None],
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
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, ...]], Character],
        debug: Callable[[...], None],
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


@pytest.mark.clean_db
class TestWerewolfAttributes:
    """Test werewolf attributes."""

    async def test_create_character_werewolf(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
    ) -> None:
        """Verify we can create a werewolf character."""
        werewolf_tribe = await WerewolfTribe.find_one({"is_archived": False})
        werewolf_auspice = await WerewolfAuspice.find_one({"is_archived": False})
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

        # Cleanup
        await character.delete()

    async def test_update_character_werewolf(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, ...]], Character],
        debug: Callable[[...], None],
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

    async def test_patch_werewolf_tribe(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        character_factory: Callable[[dict[str, ...]], Character],
        debug: Callable[[...], None],
    ) -> None:
        """Test werewolf tribe and auspice can be patched."""
        # Given a werewolf character with full werewolf attributes
        character = await character_factory(character_class="WEREWOLF")
        auspice = await WerewolfAuspice.find_one({"is_archived": False})
        tribe = await WerewolfTribe.find_one({"is_archived": False})
        character.werewolf_attributes.tribe_id = tribe.id
        character.werewolf_attributes.auspice_id = auspice.id
        character.werewolf_attributes.tribe_name = tribe.name
        character.werewolf_attributes.auspice_name = auspice.name
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
        assert response.json() == updated_character.model_dump(
            mode="json", exclude=EXCLUDE_CHARACTER_FIELDS
        )


@pytest.mark.clean_db
class TestCharacterCreate:
    """Test character create endpoints."""

    async def test_create_character(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        all_traits_in_section: Callable[[str], list[Trait]],
        debug: Callable[[...], None],
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
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        json_data: dict[str, ...],
        debug: Callable[[...], None],
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
        build_url: Callable[[str, ...], str],
        base_user: User,
        token_company_admin: dict[str, str],
        debug: Callable[[...], None],
        user_factory: Callable[[dict[str, ...]], User],
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
        build_url: Callable[[str, ...], str],
        token_company_admin: dict[str, str],
        user_factory: Callable[[dict[str, ...]], User],
        all_traits_in_section: Callable[[str], list[Trait]],
        debug: Callable[[...], None],
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
        assert character.concept_name == concept.name
        assert character.user_player_id == user_player.id
        # Add one to the size of the list b/c willpower is created
        assert len(character.character_trait_ids) == len(traits) + 1
        assert character.specialties == concept.specialties

        # Cleanup
        await character.delete()


class TestCharacterFullSheet:
    """Test character full sheet endpoint."""

    async def test_get_character_full_sheet(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        base_character: Character,
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify the full sheet endpoint returns the character with organized sections."""
        # Given a character with traits (one with subcategory, one without)
        trait_no_sub = await Trait.find_one(
            Trait.is_archived == False,
            Trait.trait_subcategory_id == None,
        )
        trait_with_sub = await Trait.find_one(
            Trait.is_archived == False,
            Trait.trait_subcategory_id != None,
        )
        assert trait_no_sub is not None
        assert trait_with_sub is not None

        await character_trait_factory(character_id=base_character.id, trait=trait_no_sub, value=3)
        await character_trait_factory(character_id=base_character.id, trait=trait_with_sub, value=2)

        # When we request the full sheet
        response = await client.get(
            build_url(CharacterURL.FULL_SHEET, character_id=base_character.id),
            headers=token_global_admin,
        )

        # Then the response is successful
        assert response.status_code == HTTP_200_OK
        data = response.json()

        # And the response contains the character
        assert data["character"]["id"] == str(base_character.id)

        # And sections are present and structured correctly with id fields
        assert len(data["sections"]) >= 1
        for section in data["sections"]:
            assert "id" in section
            assert "name" in section
            assert "categories" in section
            for category in section["categories"]:
                assert "id" in category
                assert "name" in category
                assert "subcategories" in category
                assert "character_traits" in category
                for sub in category["subcategories"]:
                    assert "id" in sub
                for ct in category["character_traits"]:
                    assert "id" in ct
                    assert "character_id" in ct

    async def test_get_character_full_sheet_with_available_traits(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        base_character: Character,
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify the full sheet endpoint includes available traits when flag is set."""
        # Given a character with one assigned trait
        assigned_trait = await Trait.find_one(
            Trait.is_archived == False,
            Trait.trait_subcategory_id == None,
            Trait.character_classes == base_character.character_class,
            Trait.game_versions == base_character.game_version,
            Trait.is_custom == False,
        )
        assert assigned_trait is not None
        await character_trait_factory(character_id=base_character.id, trait=assigned_trait, value=3)

        # When we request the full sheet with include_available_traits=true
        url = build_url(CharacterURL.FULL_SHEET, character_id=base_character.id)
        response = await client.get(
            f"{url}?include_available_traits=true",
            headers=token_global_admin,
        )

        # Then the response is successful
        assert response.status_code == HTTP_200_OK
        data = response.json()

        # And available_traits fields are present on categories and subcategories
        for section in data["sections"]:
            for category in section["categories"]:
                assert "available_traits" in category
                assert isinstance(category["available_traits"], list)
                for sub in category["subcategories"]:
                    assert "available_traits" in sub
                    assert isinstance(sub["available_traits"], list)

        # And the assigned trait does not appear in any available_traits list
        all_available_ids = set()
        for section in data["sections"]:
            for category in section["categories"]:
                all_available_ids.update(t["id"] for t in category["available_traits"])
                for sub in category["subcategories"]:
                    all_available_ids.update(t["id"] for t in sub["available_traits"])
        assert str(assigned_trait.id) not in all_available_ids

        # And at least some available traits are present (since only one trait is assigned)
        assert len(all_available_ids) > 0

    async def test_get_character_full_sheet_available_traits_empty_by_default(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_character: Character,
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify available_traits is empty when include_available_traits is not set."""
        # When we request the full sheet without the flag
        response = await client.get(
            build_url(CharacterURL.FULL_SHEET, character_id=base_character.id),
            headers=token_global_admin,
        )

        # Then the response is successful
        assert response.status_code == HTTP_200_OK
        data = response.json()

        # And all available_traits lists are empty
        for section in data["sections"]:
            for category in section["categories"]:
                assert category["available_traits"] == []
                for sub in category["subcategories"]:
                    assert sub["available_traits"] == []

    async def test_get_character_full_sheet_category(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        base_character: Character,
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify the category slice endpoint returns a single category with traits."""
        # Given a trait without a subcategory
        trait_no_sub = await Trait.find_one(
            Trait.is_archived == False,
            Trait.trait_subcategory_id == None,
        )
        assert trait_no_sub is not None

        await character_trait_factory(character_id=base_character.id, trait=trait_no_sub, value=3)

        # When we request that trait's category
        response = await client.get(
            build_url(
                CharacterURL.FULL_SHEET_CATEGORY,
                character_id=base_character.id,
                category_id=str(trait_no_sub.parent_category_id),
            ),
            headers=token_global_admin,
        )

        # Then the response is successful
        assert response.status_code == HTTP_200_OK
        data = response.json()

        # And the response contains the category with correct structure
        assert data["id"] == str(trait_no_sub.parent_category_id)
        assert "name" in data
        assert "subcategories" in data
        assert "character_traits" in data

        # And the character trait is present
        trait_ids = [ct["trait"]["id"] for ct in data["character_traits"]]
        assert str(trait_no_sub.id) in trait_ids

    async def test_get_character_full_sheet_category_with_available_traits(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        base_character: Character,
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify the category slice includes available traits when requested."""
        # Given a trait assigned to the character
        trait = await Trait.find_one(
            Trait.is_archived == False,
            Trait.trait_subcategory_id == None,
            Trait.is_custom == False,
        )
        assert trait is not None

        await character_trait_factory(character_id=base_character.id, trait=trait, value=2)

        # When we request the category with available traits
        response = await client.get(
            build_url(
                CharacterURL.FULL_SHEET_CATEGORY,
                character_id=base_character.id,
                category_id=str(trait.parent_category_id),
            ),
            params={"include_available_traits": True},
            headers=token_global_admin,
        )

        # Then the response is successful
        assert response.status_code == HTTP_200_OK
        data = response.json()

        # And available_traits is populated (non-empty for categories with multiple traits)
        all_available = data.get("available_traits", [])
        for sub in data.get("subcategories", []):
            all_available.extend(sub.get("available_traits", []))

        # And the assigned trait is NOT in available_traits
        available_ids = [t["id"] for t in all_available]
        assert str(trait.id) not in available_ids

    async def test_get_character_full_sheet_category_available_traits_default_empty(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_character: Character,
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify available traits are empty when not requested."""
        # Given a category that exists
        category = await TraitCategory.find_one(TraitCategory.is_archived == False)
        assert category is not None

        # When we request without include_available_traits
        response = await client.get(
            build_url(
                CharacterURL.FULL_SHEET_CATEGORY,
                character_id=base_character.id,
                category_id=str(category.id),
            ),
            headers=token_global_admin,
        )

        # Then available traits lists are all empty
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["available_traits"] == []
        for sub in data.get("subcategories", []):
            assert sub["available_traits"] == []

    async def test_get_character_full_sheet_category_not_found(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_character: Character,
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify 404 when category does not exist."""
        # Given a non-existent category ID
        fake_id = PydanticObjectId()

        # When we request it
        response = await client.get(
            build_url(
                CharacterURL.FULL_SHEET_CATEGORY,
                character_id=base_character.id,
                category_id=str(fake_id),
            ),
            headers=token_global_admin,
        )

        # Then we get a 404
        assert response.status_code == HTTP_404_NOT_FOUND

    async def test_get_character_full_sheet_category_empty_skeleton(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        base_character: Character,
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify an empty category returns the skeleton structure."""
        # Given a category with show_when_empty=True and no character traits
        category = await TraitCategory.find_one(
            TraitCategory.is_archived == False,
            TraitCategory.show_when_empty == True,
        )
        assert category is not None

        # When we request that category
        response = await client.get(
            build_url(
                CharacterURL.FULL_SHEET_CATEGORY,
                character_id=base_character.id,
                category_id=str(category.id),
            ),
            headers=token_global_admin,
        )

        # Then the response includes the category structure
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["id"] == str(category.id)
        assert data["show_when_empty"] is True
        assert "subcategories" in data
        assert "character_traits" in data

    async def test_get_character_full_sheet_category_out_of_class(
        self,
        client: AsyncClient,
        build_url: Callable[[str, ...], str],
        character_trait_factory: Callable[[dict[str, ...]], CharacterTrait],
        base_character: Character,
        token_global_admin: dict[str, str],
    ) -> None:
        """Verify out-of-class category returns traits granted by storyteller."""
        # Given a trait from a different character class than the base character
        trait = await Trait.find_one(
            Trait.is_archived == False,
            Trait.character_classes != base_character.character_class,
            Trait.trait_subcategory_id == None,
        )
        assert trait is not None

        # And the trait is assigned to the character (storyteller grant)
        await character_trait_factory(character_id=base_character.id, trait=trait, value=1)

        # When we request that trait's category
        response = await client.get(
            build_url(
                CharacterURL.FULL_SHEET_CATEGORY,
                character_id=base_character.id,
                category_id=str(trait.parent_category_id),
            ),
            headers=token_global_admin,
        )

        # Then the response is successful and includes the out-of-class trait
        assert response.status_code == HTTP_200_OK
        data = response.json()
        trait_ids = [ct["trait"]["id"] for ct in data["character_traits"]]
        assert str(trait.id) in trait_ids
