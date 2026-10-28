"""Test that IDs from another company or another owner are rejected across endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND

from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.domain.urls import Characters, DiceRolls, Users

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.campaign import Campaign
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.user import User

pytestmark = pytest.mark.anyio

_CHARACTER_BODY = {
    "name_first": "Test",
    "name_last": "Character",
    "character_class": "MORTAL",
    "game_version": "V5",
    "type": "PLAYER",
}


async def test_on_behalf_of_user_from_another_company_is_rejected(
    client: AsyncClient,
    build_url: Callable[..., str],
    token_company_user: dict[str, str],
    session_company: Company,
    session_campaign: Campaign,
    company_factory: Callable[..., Any],
    user_factory: Callable[..., Any],
) -> None:
    """Verify On-Behalf-Of must name a user in the path company."""
    # Given a user in a company the developer cannot access
    foreign_user = await user_factory(company=await company_factory())

    # When the developer acts as that user in its own company
    response = await client.post(
        build_url(Characters.CREATE, company_id=session_company.id),
        headers=token_company_user | {"On-Behalf-Of": str(foreign_user.id)},
        json=_CHARACTER_BODY | {"campaign_id": str(session_campaign.id)},
    )

    # Then the acting user is not found
    assert response.status_code == HTTP_404_NOT_FOUND


async def test_character_create_rejects_campaign_from_another_company(
    client: AsyncClient,
    build_url: Callable[..., str],
    token_global_admin: dict[str, str],
    session_company: Company,
    session_user_admin: User,
    company_factory: Callable[..., Any],
    campaign_factory: Callable[..., Any],
) -> None:
    """Verify a character cannot reference another company's campaign."""
    # Given a campaign in another company
    foreign_campaign = await campaign_factory(company=await company_factory())

    # When creating a character that references it
    response = await client.post(
        build_url(Characters.CREATE, company_id=session_company.id),
        headers=token_global_admin | {"On-Behalf-Of": str(session_user_admin.id)},
        json=_CHARACTER_BODY | {"campaign_id": str(foreign_campaign.id)},
    )

    # Then the request is rejected
    assert response.status_code in {HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND}


async def test_character_create_rejects_player_from_another_company(
    client: AsyncClient,
    build_url: Callable[..., str],
    token_global_admin: dict[str, str],
    session_company: Company,
    session_campaign: Campaign,
    session_user_admin: User,
    company_factory: Callable[..., Any],
    user_factory: Callable[..., Any],
) -> None:
    """Verify a character cannot name another company's user as its player."""
    # Given a user in another company
    foreign_user = await user_factory(company=await company_factory())

    # When creating a character with that user as player
    response = await client.post(
        build_url(Characters.CREATE, company_id=session_company.id),
        headers=token_global_admin | {"On-Behalf-Of": str(session_user_admin.id)},
        json=_CHARACTER_BODY
        | {"campaign_id": str(session_campaign.id)}
        | {"user_player_id": str(foreign_user.id)},
    )

    # Then the request is rejected
    assert response.status_code in {HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND}


async def test_asset_delete_rejects_asset_from_another_company(
    client: AsyncClient,
    build_url: Callable[..., str],
    token_company_user: dict[str, str],
    session_company: Company,
    session_user: User,
    s3asset_factory: Callable[..., Any],
) -> None:
    """Verify an asset in another company cannot be deleted through this company."""
    # Given an asset in another company
    foreign_asset = await s3asset_factory()

    # When deleting it through a user in this company
    response = await client.delete(
        build_url(
            Users.ASSET_DELETE,
            company_id=session_company.id,
            user_id=session_user.id,
            asset_id=foreign_asset.id,
        ),
        headers=token_company_user | {"On-Behalf-Of": str(session_user.id)},
    )

    # Then the asset is not found and still exists
    assert response.status_code == HTTP_404_NOT_FOUND
    assert await S3Asset.filter(id=foreign_asset.id).exists()


async def test_asset_delete_rejects_asset_of_another_parent(
    client: AsyncClient,
    build_url: Callable[..., str],
    token_company_user: dict[str, str],
    session_company: Company,
    user_factory: Callable[..., Any],
    s3asset_factory: Callable[..., Any],
) -> None:
    """Verify a user's asset route cannot delete another user's asset."""
    # Given two players and an asset belonging to the second
    player = await user_factory(company=session_company)
    other_player = await user_factory(company=session_company)
    asset = await s3asset_factory(company=session_company, user_parent=other_player)

    # When the first player deletes it through their own asset route
    response = await client.delete(
        build_url(
            Users.ASSET_DELETE,
            company_id=session_company.id,
            user_id=player.id,
            asset_id=asset.id,
        ),
        headers=token_company_user | {"On-Behalf-Of": str(player.id)},
    )

    # Then the asset is not found and still exists
    assert response.status_code == HTTP_404_NOT_FOUND
    assert await S3Asset.filter(id=asset.id).exists()


async def test_quickroll_update_rejects_another_users_quickroll(
    client: AsyncClient,
    build_url: Callable[..., str],
    token_company_user: dict[str, str],
    session_company: Company,
    user_factory: Callable[..., Any],
    quickroll_factory: Callable[..., Any],
) -> None:
    """Verify a user cannot edit another user's quickroll through their own path."""
    # Given two players and a quickroll belonging to the second
    player = await user_factory(company=session_company)
    other_player = await user_factory(company=session_company)
    quickroll = await quickroll_factory(user=other_player, name="original")

    # When the first player renames it through their own quickroll route
    response = await client.patch(
        build_url(
            Users.QUICKROLL_UPDATE,
            company_id=session_company.id,
            user_id=player.id,
            quickroll_id=quickroll.id,
        ),
        headers=token_company_user | {"On-Behalf-Of": str(player.id)},
        json={"name": "renamed"},
    )

    # Then the quickroll is not found and unchanged
    assert response.status_code == HTTP_404_NOT_FOUND
    assert (await QuickRoll.get(id=quickroll.id)).name == "original"


async def test_quickroll_roll_rejects_character_from_another_company(
    client: AsyncClient,
    build_url: Callable[..., str],
    token_company_user: dict[str, str],
    session_company: Company,
    user_factory: Callable[..., Any],
    character_factory: Callable[..., Any],
    character_trait_factory: Callable[..., Any],
    quickroll_factory: Callable[..., Any],
) -> None:
    """Verify a quickroll cannot be rolled against another company's character."""
    # Given a character with a trait in another company, and a quickroll for that trait here
    trait = await Trait.filter(is_archived=False).first()
    foreign_character = await character_factory()
    await character_trait_factory(character=foreign_character, trait=trait)
    player = await user_factory(company=session_company)
    quickroll = await quickroll_factory(user=player, traits=[trait])

    # When rolling the quickroll against the foreign character
    response = await client.post(
        build_url(DiceRolls.QUICKROLL, company_id=session_company.id),
        headers=token_company_user | {"On-Behalf-Of": str(player.id)},
        json={"quickroll_id": str(quickroll.id), "character_id": str(foreign_character.id)},
    )

    # Then the character is rejected
    assert response.status_code in {HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND}
