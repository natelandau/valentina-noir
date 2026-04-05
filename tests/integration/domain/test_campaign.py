"""Test campaign."""

from collections.abc import Callable

import pytest
from httpx import AsyncClient
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_403_FORBIDDEN,
    HTTP_404_NOT_FOUND,
)

from vapi.constants import PermissionManageCampaign, UserRole
from vapi.db.sql_models.campaign import Campaign
from vapi.db.sql_models.company import Company, CompanySettings
from vapi.db.sql_models.user import User
from vapi.domain.urls import Campaigns

pytestmark = pytest.mark.anyio


class TestListCampaigns:
    """Test list campaigns."""

    async def test_list_campaigns(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        session_company: Company,
        session_global_admin,
        session_user: User,
        campaign_factory: Callable[..., Campaign],
        build_url: Callable[..., str],
    ) -> None:
        """Verify listing campaigns returns only company-scoped results."""
        # Given a company with one campaign
        campaign = await campaign_factory(company=session_company)

        # When we list the campaigns
        response = await client.get(
            build_url(
                Campaigns.LIST,
                company_id=session_company.id,
                user_id=session_user.id,
            ),
            headers=token_global_admin,
        )

        # Then we should get a 200 with the campaign in the list
        assert response.status_code == HTTP_200_OK
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == str(campaign.id)
        assert items[0]["name"] == campaign.name
        assert response.json()["total"] == 1


class TestGetCampaign:
    """Test get campaign."""

    async def test_get_campaign(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        session_company: Company,
        session_global_admin,
        session_user: User,
        campaign_factory: Callable[..., Campaign],
        build_url: Callable[..., str],
    ) -> None:
        """Verify getting a campaign by ID."""
        # Given a campaign
        campaign = await campaign_factory(company=session_company)

        # When we get the campaign
        response = await client.get(
            build_url(
                Campaigns.DETAIL,
                campaign_id=campaign.id,
                company_id=session_company.id,
                user_id=session_user.id,
            ),
            headers=token_global_admin,
        )

        # Then we should get a 200 with the campaign details
        assert response.status_code == HTTP_200_OK
        assert response.json()["id"] == str(campaign.id)
        assert response.json()["name"] == campaign.name

    async def test_get_campaign_wrong_company(
        self,
        client: AsyncClient,
        token_global_admin: dict[str, str],
        session_company: Company,
        session_global_admin,
        session_user: User,
        company_factory: Callable[..., Company],
        campaign_factory: Callable[..., Campaign],
        build_url: Callable[..., str],
    ) -> None:
        """Verify get returns 404 when campaign belongs to a different company."""
        # Given a campaign belonging to a different company
        other_company = await company_factory(name="Other Co", email="other@example.com")
        campaign = await campaign_factory(company=other_company)

        # When we get the campaign under the wrong company
        response = await client.get(
            build_url(
                Campaigns.DETAIL,
                campaign_id=campaign.id,
                company_id=session_company.id,
                user_id=session_user.id,
            ),
            headers=token_global_admin,
        )

        # Then we should get a 404
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
        session_company: Company,
        session_global_admin,
        user_factory: Callable[..., User],
        build_url: Callable[..., str],
        campaign_permission: PermissionManageCampaign,
        user_role: UserRole,
        expected_status_code: int,
    ) -> None:
        """Verify create campaign respects permission settings."""
        # Given a company with a specific campaign permission
        await CompanySettings.filter(company_id=session_company.id).update(
            permission_manage_campaign=campaign_permission
        )
        user = await user_factory(company=session_company, role=user_role.value)

        # When we create the campaign
        response = await client.post(
            build_url(
                Campaigns.CREATE,
                company_id=session_company.id,
                user_id=user.id,
            ),
            headers=token_global_admin,
            json={"name": "Test Campaign", "description": "Test Description", "danger": 1},
        )

        # Then we should get the expected status code
        assert response.status_code == expected_status_code
        if expected_status_code == HTTP_201_CREATED:
            assert response.json()["name"] == "Test Campaign"
            assert response.json()["description"] == "Test Description"
            assert response.json()["company_id"] == str(session_company.id)
            assert response.json()["desperation"] == 0
            assert response.json()["danger"] == 1
            assert response.json()["date_created"] is not None
            assert response.json()["date_modified"] is not None

            campaign = await Campaign.get(id=response.json()["id"])
            assert campaign.name == "Test Campaign"


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
        session_company: Company,
        session_global_admin,
        user_factory: Callable[..., User],
        campaign_factory: Callable[..., Campaign],
        build_url: Callable[..., str],
        campaign_permission: PermissionManageCampaign,
        user_role: UserRole,
        expected_status_code: int,
    ) -> None:
        """Verify update campaign respects permission settings."""
        # Given a company with a campaign and specific permission
        await CompanySettings.filter(company_id=session_company.id).update(
            permission_manage_campaign=campaign_permission
        )
        user = await user_factory(company=session_company, role=user_role.value)
        campaign = await campaign_factory(
            company=session_company,
            name="original",
            description="original description",
            danger=1,
            desperation=3,
        )

        # When we update the campaign
        response = await client.patch(
            build_url(
                Campaigns.UPDATE,
                company_id=session_company.id,
                campaign_id=campaign.id,
                user_id=user.id,
            ),
            headers=token_global_admin,
            json={
                "name": "Test Campaign Updated",
                "description": "Test Description Updated",
                "danger": 2,
            },
        )

        # Then we should get the expected status code
        assert response.status_code == expected_status_code
        if expected_status_code == HTTP_200_OK:
            assert response.json()["name"] == "Test Campaign Updated"
            assert response.json()["description"] == "Test Description Updated"
            assert response.json()["company_id"] == str(session_company.id)
            assert response.json()["desperation"] == 3
            assert response.json()["danger"] == 2

            await campaign.refresh_from_db()
            assert campaign.name == "Test Campaign Updated"


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
        session_company: Company,
        session_global_admin,
        user_factory: Callable[..., User],
        campaign_factory: Callable[..., Campaign],
        build_url: Callable[..., str],
        user_role: UserRole,
        campaign_permission: PermissionManageCampaign,
        expected_status_code: int,
    ) -> None:
        """Verify delete campaign respects permission settings."""
        # Given a company with a campaign and specific permission
        await CompanySettings.filter(company_id=session_company.id).update(
            permission_manage_campaign=campaign_permission
        )
        user = await user_factory(company=session_company, role=user_role.value)
        campaign = await campaign_factory(
            company=session_company,
            name="original",
        )

        # When we delete the campaign
        response = await client.delete(
            build_url(
                Campaigns.DELETE,
                company_id=session_company.id,
                campaign_id=campaign.id,
                user_id=user.id,
            ),
            headers=token_global_admin,
        )

        # Then we should get the expected status code
        assert response.status_code == expected_status_code
        if expected_status_code == HTTP_204_NO_CONTENT:
            await campaign.refresh_from_db()
            assert campaign.is_archived
            assert campaign.archive_date is not None
