"""Test campaign."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_403_FORBIDDEN,
)

from vapi.constants import UserRole
from vapi.domain.urls import Campaigns

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.models import Campaign, Company, User

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    "user_role",
    [
        (UserRole.ADMIN),
        (UserRole.STORYTELLER),
        (UserRole.PLAYER),
    ],
)
async def test_campaign_controller(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    base_company: Company,
    user_role: UserRole,
    base_campaign: Campaign,
    build_url: Callable[[str, ...], str],
    base_user_storyteller: User,
    base_user_admin: User,
    base_user_player: User,
    debug: Callable[[...], None],
) -> None:
    """Verify the campaign controller."""
    if user_role == UserRole.STORYTELLER:
        user = base_user_storyteller
    elif user_role == UserRole.ADMIN:
        user = base_user_admin
    elif user_role == UserRole.PLAYER:
        user = base_user_player

    assert user is not None

    response = await client.post(
        build_url(Campaigns.CREATE, user_id=user.id),
        headers=token_company_admin,
        json={"name": "Test Campaign", "description": "Test Description", "danger": 1},
    )
    if user_role == UserRole.PLAYER:
        assert response.status_code == HTTP_403_FORBIDDEN
    else:
        assert response.status_code == HTTP_201_CREATED
        # debug(response.json())
        response_json = response.json()
        assert response_json["name"] == "Test Campaign"
        assert response_json["description"] == "Test Description"
        assert response_json["company_id"] == str(base_company.id)
        assert response_json["desperation"] == 0
        assert response_json["danger"] == 1
        assert response_json["date_created"] is not None
        assert response_json["date_modified"] is not None
        assert not response_json.get("is_archived")

    # get the new campaign id
    new_campaign_id = response_json["id"] if user_role != UserRole.PLAYER else base_campaign.id

    response = await client.patch(
        build_url(Campaigns.UPDATE, campaign_id=new_campaign_id, user_id=user.id),
        headers=token_company_admin,
        json={
            "name": "Test Campaign Updated",
            "description": "Test Description Updated",
            "desperation": 4,
        },
    )
    if user_role == UserRole.PLAYER:
        assert response.status_code == HTTP_403_FORBIDDEN
    else:
        # debug(response.json())
        assert response.status_code == HTTP_200_OK
        assert response.json()["name"] == "Test Campaign Updated"
        assert response.json()["description"] == "Test Description Updated"
        assert response.json()["company_id"] == str(base_company.id)
        assert response.json()["desperation"] == 4
        assert response.json()["danger"] == 1
        assert response.json()["date_modified"] is not None

    response = await client.delete(
        build_url(Campaigns.DELETE, campaign_id=new_campaign_id, user_id=user.id),
        headers=token_company_admin,
    )
    if user_role == UserRole.PLAYER:
        assert response.status_code == HTTP_403_FORBIDDEN
    else:
        assert response.status_code == HTTP_204_NO_CONTENT

    response = await client.get(
        build_url(Campaigns.LIST, user_id=user.id), headers=token_company_admin
    )
    # debug(response.json())
    assert response.status_code == HTTP_200_OK
    assert response.json()["items"] == [
        base_campaign.model_dump(mode="json", exclude={"is_archived", "archive_date"})
    ]

    response = await client.get(
        build_url(Campaigns.DETAIL, campaign_id=base_campaign.id, user_id=user.id),
        headers=token_company_admin,
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == base_campaign.model_dump(
        mode="json", exclude={"is_archived", "archive_date"}
    )


@pytest.mark.parametrize(
    "user_role",
    [
        (UserRole.ADMIN),
        (UserRole.STORYTELLER),
        (UserRole.PLAYER),
    ],
)
async def test_campaign_set_desperation(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    base_company: Company,
    base_campaign: Campaign,
    user_role: UserRole,
    base_user_storyteller: User,
    base_user_admin: User,
    base_user_player: User,
    build_url: Callable[[str, ...], str],
) -> None:
    """Verify the campaign set desperation endpoint."""
    if user_role == UserRole.STORYTELLER:
        user = base_user_storyteller
    elif user_role == UserRole.ADMIN:
        user = base_user_admin
    elif user_role == UserRole.PLAYER:
        user = base_user_player

    assert user is not None

    base_campaign.desperation = 0
    await base_campaign.save()

    response = await client.put(
        build_url(Campaigns.SET_DESPERATION, campaign_id=base_campaign.id, user_id=user.id),
        headers=token_company_admin,
        params={"desperation": 1},
    )
    if user_role == UserRole.PLAYER:
        assert response.status_code == HTTP_403_FORBIDDEN
    else:
        assert response.status_code == HTTP_200_OK
        await base_campaign.sync()
        assert base_campaign.desperation == 1


@pytest.mark.parametrize(
    "user_role",
    [
        (UserRole.ADMIN),
        (UserRole.STORYTELLER),
        (UserRole.PLAYER),
    ],
)
async def test_campaign_set_danger(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    base_campaign: Campaign,
    user_role: UserRole,
    base_user_storyteller: User,
    base_user_admin: User,
    base_user_player: User,
    build_url: Callable[[str, ...], str],
) -> None:
    """Verify the campaign set danger endpoint."""
    if user_role == UserRole.STORYTELLER:
        user = base_user_storyteller
    elif user_role == UserRole.ADMIN:
        user = base_user_admin
    elif user_role == UserRole.PLAYER:
        user = base_user_player

    assert user is not None

    base_campaign.danger = 0
    await base_campaign.save()

    response = await client.put(
        build_url(Campaigns.SET_DANGER, campaign_id=base_campaign.id, user_id=user.id),
        headers=token_company_admin,
        params={"danger": 1},
    )
    if user_role == UserRole.PLAYER:
        assert response.status_code == HTTP_403_FORBIDDEN
    else:
        assert response.status_code == HTTP_200_OK
        await base_campaign.sync()
        assert base_campaign.danger == 1
