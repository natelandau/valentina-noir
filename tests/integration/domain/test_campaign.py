"""Test campaign."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from beanie import PydanticObjectId
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from vapi.constants import PermissionManageCampaign, UserRole
from vapi.db.models import Campaign
from vapi.domain.urls import Campaigns

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.models import Company, User

pytestmark = pytest.mark.anyio


class TestListCampaigns:
    """Test list campaigns."""

    async def test_list_campaigns(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        company_factory: Callable[[], Company],
        campaign_factory: Callable[[], Campaign],
        build_url: Callable[[str, ...], str],
    ) -> None:
        """Test list campaigns."""
        # Given a company and a campaign
        company = await company_factory()
        campaign = await campaign_factory(company_id=company.id)
        await campaign_factory(company_id=PydanticObjectId())

        # When we list the campaigns
        response = await client.get(
            build_url(Campaigns.LIST, company_id=company.id), headers=token_global_admin
        )

        # Then we should get a 200 ok response with the campaign in the list
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "items": [campaign.model_dump(mode="json", exclude={"is_archived", "archive_date"})],
            "limit": 10,
            "offset": 0,
            "total": 1,
        }


class TestGetCampaign:
    """Test get campaign."""

    async def test_get_campaign(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        company_factory: Callable[[], Company],
        campaign_factory: Callable[[], Campaign],
        build_url: Callable[[str, ...], str],
        user_factory: Callable[[], User],
    ) -> None:
        """Verify the get campaign endpoint."""
        # Given a company and a campaign
        company = await company_factory()
        campaign = await campaign_factory(company_id=company.id)

        # When we get the campaign
        response = await client.get(
            build_url(
                Campaigns.DETAIL,
                campaign_id=campaign.id,
                company_id=company.id,
            ),
            headers=token_global_admin,
        )

        # Then we should get a 200 ok response with the campaign
        assert response.status_code == HTTP_200_OK
        assert response.json() == campaign.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )

    async def test_get_campaign_wrong_company(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        company_factory: Callable[[], Company],
        campaign_factory: Callable[[], Campaign],
        build_url: Callable[[str, ...], str],
    ) -> None:
        """Verify the get campaign endpoint."""
        # Given a company and a campaign
        company = await company_factory()
        campaign = await campaign_factory(company_id=PydanticObjectId())

        # When we get the campaign
        response = await client.get(
            build_url(Campaigns.DETAIL, campaign_id=campaign.id, company_id=company.id),
            headers=token_global_admin,
        )

        # Then we should get a 404 not found response
        assert response.status_code == HTTP_404_NOT_FOUND


class TestCreateCampaign:
    """Test create campaign."""

    @pytest.mark.parametrize(
        ("user_role", "campaign_permission", "expected_status_code"),
        [
            (UserRole.ADMIN, PermissionManageCampaign.UNRESTRICTED, HTTP_201_CREATED),
            (UserRole.ADMIN, PermissionManageCampaign.STORYTELLER, HTTP_201_CREATED),
            (UserRole.STORYTELLER, PermissionManageCampaign.STORYTELLER, HTTP_201_CREATED),
            (UserRole.STORYTELLER, PermissionManageCampaign.UNRESTRICTED, HTTP_201_CREATED),
            (UserRole.PLAYER, PermissionManageCampaign.UNRESTRICTED, HTTP_201_CREATED),
            (UserRole.PLAYER, PermissionManageCampaign.STORYTELLER, HTTP_403_FORBIDDEN),
        ],
    )
    async def test_create_campaign(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        company_factory: Callable[[], Company],
        campaign_factory: Callable[[], Campaign],
        build_url: Callable[[str, ...], str],
        user_factory: Callable[[], User],
        campaign_permission: PermissionManageCampaign,
        user_role: UserRole,
        expected_status_code: int,
        debug: Callable[[...], None],
    ) -> None:
        """Test create campaign."""
        # Given a company and a campaign
        company = await company_factory()
        company.settings.permission_manage_campaign = campaign_permission
        await company.save()
        user = await user_factory(company_id=company.id, role=user_role)

        # When we create the campaign
        response = await client.post(
            build_url(Campaigns.CREATE, company_id=company.id, user_id=user.id),
            headers=token_global_admin,
            json={"name": "Test Campaign", "description": "Test Description", "danger": 1},
        )

        # Then we should get the expected status code
        assert response.status_code == expected_status_code
        if expected_status_code == HTTP_201_CREATED:
            assert response.json()["name"] == "Test Campaign"
            assert response.json()["description"] == "Test Description"
            assert response.json()["company_id"] == str(company.id)
            assert response.json()["desperation"] == 0
            assert response.json()["danger"] == 1
            assert response.json()["date_created"] is not None
            assert response.json()["date_modified"] is not None

            campaign = await Campaign.get(response.json()["id"])
            assert campaign.name == "Test Campaign"
            assert campaign.description == "Test Description"
            assert campaign.company_id == company.id
            assert campaign.desperation == 0
            assert campaign.danger == 1
            assert campaign.date_created is not None
            assert campaign.date_modified is not None


class TestUpdateCampaign:
    """Test update campaign."""

    @pytest.mark.parametrize(
        ("user_role", "campaign_permission", "expected_status_code"),
        [
            (UserRole.ADMIN, PermissionManageCampaign.UNRESTRICTED, HTTP_200_OK),
            (UserRole.ADMIN, PermissionManageCampaign.STORYTELLER, HTTP_200_OK),
            (UserRole.STORYTELLER, PermissionManageCampaign.STORYTELLER, HTTP_200_OK),
            (UserRole.STORYTELLER, PermissionManageCampaign.UNRESTRICTED, HTTP_200_OK),
            (UserRole.PLAYER, PermissionManageCampaign.UNRESTRICTED, HTTP_200_OK),
            (UserRole.PLAYER, PermissionManageCampaign.STORYTELLER, HTTP_403_FORBIDDEN),
        ],
    )
    async def test_update_campaign(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        company_factory: Callable[[], Company],
        campaign_factory: Callable[[], Campaign],
        build_url: Callable[[str, ...], str],
        user_factory: Callable[[], User],
        campaign_permission: PermissionManageCampaign,
        user_role: UserRole,
        expected_status_code: int,
        debug: Callable[[...], None],
    ) -> None:
        """Test update campaign."""
        # Given a company and a campaign
        company = await company_factory()
        company.settings.permission_manage_campaign = campaign_permission
        await company.save()
        user = await user_factory(company_id=company.id, role=user_role)
        campaign = await campaign_factory(
            company_id=company.id,
            name="original",
            description="original description",
            danger=1,
            desperation=3,
        )
        # debug(campaign)

        # When we update the campaign
        response = await client.patch(
            build_url(
                Campaigns.UPDATE, company_id=company.id, campaign_id=campaign.id, user_id=user.id
            ),
            headers=token_global_admin,
            json={
                "name": "Test Campaign Updated",
                "description": "Test Description Updated",
                "danger": 2,
            },
        )
        # debug(response.json())

        # Then we should get the expected status code
        assert response.status_code == expected_status_code

        if expected_status_code == HTTP_200_OK:
            assert response.json()["name"] == "Test Campaign Updated"
            assert response.json()["description"] == "Test Description Updated"
            assert response.json()["company_id"] == str(company.id)
            assert response.json()["desperation"] == 3
            assert response.json()["danger"] == 2

            await campaign.sync()
            assert campaign.name == "Test Campaign Updated"
            assert campaign.description == "Test Description Updated"
            assert campaign.company_id == company.id
            assert campaign.desperation == 3
            assert campaign.danger == 2


class TestDeleteCampaign:
    """Test delete campaign."""

    @pytest.mark.parametrize(
        ("user_role", "campaign_permission", "expected_status_code"),
        [
            (UserRole.ADMIN, PermissionManageCampaign.UNRESTRICTED, HTTP_204_NO_CONTENT),
            (UserRole.ADMIN, PermissionManageCampaign.STORYTELLER, HTTP_204_NO_CONTENT),
            (UserRole.STORYTELLER, PermissionManageCampaign.STORYTELLER, HTTP_204_NO_CONTENT),
            (UserRole.STORYTELLER, PermissionManageCampaign.UNRESTRICTED, HTTP_204_NO_CONTENT),
            (UserRole.PLAYER, PermissionManageCampaign.UNRESTRICTED, HTTP_204_NO_CONTENT),
            (UserRole.PLAYER, PermissionManageCampaign.STORYTELLER, HTTP_403_FORBIDDEN),
        ],
    )
    async def test_delete_campaign(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        company_factory: Callable[[], Company],
        campaign_factory: Callable[[], Campaign],
        build_url: Callable[[str, ...], str],
        user_factory: Callable[[], User],
        user_role: UserRole,
        campaign_permission: PermissionManageCampaign,
        expected_status_code: int,
        debug: Callable[[...], None],
    ) -> None:
        """Test delete campaign."""
        # Given a company and a campaign
        company = await company_factory()
        company.settings.permission_manage_campaign = campaign_permission
        await company.save()
        user = await user_factory(company_id=company.id, role=user_role)
        campaign = await campaign_factory(
            company_id=company.id,
            name="original",
            description="original description",
            danger=1,
            desperation=3,
        )
        # debug(campaign)

        # When we delete the campaign
        response = await client.delete(
            build_url(
                Campaigns.DELETE, company_id=company.id, campaign_id=campaign.id, user_id=user.id
            ),
            headers=token_global_admin,
        )
        # debug(response.json())

        # Then we should get the expected status code
        assert response.status_code == expected_status_code

        if expected_status_code == HTTP_204_NO_CONTENT:
            await campaign.sync()
            assert campaign.is_archived
            assert campaign.archive_date is not None
