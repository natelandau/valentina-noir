"""Test user."""

from __future__ import annotations

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

from vapi.constants import UserRole
from vapi.db.models import AuditLog, QuickRoll, Trait, User
from vapi.db.models.user import CampaignExperience
from vapi.domain.urls import Users as UsersURL

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.models import Campaign, Company, Developer

pytestmark = pytest.mark.anyio


class TestExperienceController:
    """Test ExperienceController."""

    async def test_get_experience_detail_no_experience(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        user_factory: Callable[[dict[str, Any]], User],
        base_campaign: Campaign,
        token_company_user: dict[str, str],
        debug: Callable[[Any], None],
    ) -> None:
        """Test get experience detail."""
        user = await user_factory()

        response = await client.get(
            build_url(UsersURL.EXPERIENCE_CAMPAIGN, user_id=user.id),
            headers=token_company_user,
        )

        assert response.status_code == HTTP_200_OK
        assert response.json() == CampaignExperience(
            campaign_id=PydanticObjectId(base_campaign.id)
        ).model_dump(mode="json", exclude={"is_archived", "archive_date"})

        # clean up
        await user.delete()

    async def test_get_experience_with_experience(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        base_campaign: Campaign,
        token_company_user: dict[str, str],
        user_factory: Callable[[dict[str, Any]], User],
    ) -> None:
        """Test get experience detail."""
        user = await user_factory()
        campaign_experience = CampaignExperience(
            campaign_id=PydanticObjectId(base_campaign.id),
            xp_current=100,
            xp_total=200,
            cool_points=100,
        )
        user.campaign_experience.append(campaign_experience)
        await user.save()

        response = await client.get(
            build_url(UsersURL.EXPERIENCE_CAMPAIGN, user_id=user.id),
            headers=token_company_user,
        )

        assert response.status_code == HTTP_200_OK
        assert response.json() == campaign_experience.model_dump(
            mode="json", exclude={"is_archived", "archive_date", "discord_oauth"}
        )

    async def test_add_xp_to_experience(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        base_campaign: Campaign,
        base_company: Company,
        base_user: User,
        user_factory: Callable[[dict[str, Any]], User],
        debug: Callable[[Any], None],
        token_company_user: dict[str, str],
    ) -> None:
        """Test add xp to experience."""
        user = await user_factory()
        response = await client.post(
            build_url(UsersURL.XP_ADD, user_id=user.id),
            headers=token_company_user,
            json={
                "amount": 100,
                "requesting_user_id": str(base_user.id),
                "campaign_id": str(base_campaign.id),
            },
        )
        assert response.status_code == HTTP_201_CREATED
        assert response.json() == CampaignExperience(
            campaign_id=PydanticObjectId(base_campaign.id),
            xp_current=100,
            xp_total=100,
            cool_points=0,
        ).model_dump(mode="json", exclude={"is_archived", "archive_date", "discord_oauth"})

        await user.sync()
        assert user.campaign_experience[0].xp_current == 100
        assert user.campaign_experience[0].xp_total == 100
        assert user.campaign_experience[0].cool_points == 0

        audit_log = await AuditLog.find_one(
            AuditLog.handler_name == "add_xp_to_campaign_experience"
        )
        # debug(audit_log)
        assert audit_log is not None
        assert audit_log.method == "POST"
        assert audit_log.request_json == {
            "amount": 100,
            "requesting_user_id": str(base_user.id),
            "campaign_id": str(base_campaign.id),
        }
        assert audit_log.path_params == {
            "company_id": str(base_company.id),
            "user_id": str(user.id),
        }
        assert audit_log.query_params == {}

    async def test_add_cp_to_experience(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        base_campaign: Campaign,
        base_company: Company,
        base_user: User,
        user_factory: Callable[[dict[str, Any]], User],
        debug: Callable[[Any], None],
        token_company_user: dict[str, str],
    ) -> None:
        """Test add cp to experience."""
        user = await user_factory()
        response = await client.post(
            build_url(UsersURL.CP_ADD, user_id=user.id),
            headers=token_company_user,
            json={
                "amount": 1,
                "requesting_user_id": str(base_user.id),
                "campaign_id": str(base_campaign.id),
            },
        )
        assert response.status_code == HTTP_201_CREATED
        assert response.json() == CampaignExperience(
            campaign_id=PydanticObjectId(base_campaign.id),
            xp_current=10,
            xp_total=10,
            cool_points=1,
        ).model_dump(mode="json", exclude={"is_archived", "archive_date"})

        await user.sync()
        assert user.campaign_experience[0].xp_current == 10
        assert user.campaign_experience[0].xp_total == 10
        assert user.campaign_experience[0].cool_points == 1

        audit_log = await AuditLog.find_one(
            AuditLog.handler_name == "add_cp_to_campaign_experience"
        )
        # debug(audit_log)
        assert audit_log is not None
        assert audit_log.method == "POST"
        assert audit_log.request_json == {
            "amount": 1,
            "requesting_user_id": str(base_user.id),
            "campaign_id": str(base_campaign.id),
        }
        assert audit_log.path_params == {
            "company_id": str(base_company.id),
            "user_id": str(user.id),
        }
        assert audit_log.query_params == {}

    async def test_remove_xp_from_experience(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        user_factory: Callable[[dict[str, Any]], User],
        base_campaign: Campaign,
        base_company: Company,
        base_user: User,
        base_developer_company_user: Developer,
        token_company_user: dict[str, str],
        debug: Callable[[Any], None],
    ) -> None:
        """Test remove xp from experience."""
        user = await user_factory()
        campaign_experience = CampaignExperience(
            campaign_id=PydanticObjectId(base_campaign.id),
            xp_current=10,
            xp_total=10,
            cool_points=1,
        )
        user.campaign_experience.append(campaign_experience)
        await user.save()

        response = await client.post(
            build_url(UsersURL.XP_REMOVE, user_id=user.id),
            headers=token_company_user,
            json={
                "amount": 6,
                "requesting_user_id": str(base_user.id),
                "campaign_id": str(base_campaign.id),
            },
        )
        assert response.status_code == HTTP_201_CREATED
        assert response.json() == CampaignExperience(
            campaign_id=PydanticObjectId(base_campaign.id),
            xp_current=4,
            xp_total=10,
            cool_points=1,
        ).model_dump(mode="json", exclude={"is_archived", "archive_date"})

        await user.sync()
        assert user.campaign_experience[0].xp_current == 4
        assert user.campaign_experience[0].xp_total == 10
        assert user.campaign_experience[0].cool_points == 1

        audit_log = await AuditLog.find_one(
            AuditLog.handler_name == "remove_xp_from_campaign_experience"
        )
        # debug(audit_log)
        assert audit_log is not None
        assert audit_log.method == "POST"
        assert audit_log.request_json == {
            "amount": 6,
            "requesting_user_id": str(base_user.id),
            "campaign_id": str(base_campaign.id),
        }
        assert audit_log.path_params == {
            "company_id": str(base_company.id),
            "user_id": str(user.id),
        }
        assert audit_log.query_params == {}
        assert audit_log.developer_id == base_developer_company_user.id


class TestUserController:
    """Test UserController."""

    class TestListUsers:
        """Test ListUsers."""

        async def test_list_users_no_results(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            company_factory: Callable[[dict[str, Any]], Company],
            user_factory: Callable[[dict[str, Any]], User],
            debug: Callable[[Any], None],
        ) -> None:
            """Test list users no results."""
            # Given a company
            company = await company_factory()

            # When we list users
            response = await client.get(
                build_url(UsersURL.LIST, company_id=company.id), headers=token_global_admin
            )

            # Then we get no users
            assert response.status_code == HTTP_200_OK
            assert response.json() == {"items": [], "limit": 10, "offset": 0, "total": 0}

            # Cleanup
            await company.delete()

        async def test_list_users_with_results(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            company_factory: Callable[[dict[str, Any]], Company],
            user_factory: Callable[[dict[str, Any]], User],
            debug: Callable[[Any], None],
        ) -> None:
            """Test list users with results."""
            # Given objects
            company = await company_factory()
            user1 = await user_factory(company_id=company.id, role=UserRole.ADMIN)
            user2 = await user_factory(company_id=company.id, role=UserRole.PLAYER)
            user3 = await user_factory(company_id=PydanticObjectId())

            # When we list users
            response = await client.get(
                build_url(UsersURL.LIST, company_id=company.id), headers=token_global_admin
            )

            # Then we get the users
            assert response.status_code == HTTP_200_OK
            assert response.json() == {
                "items": [
                    user1.model_dump(
                        mode="json", exclude={"is_archived", "archive_date", "discord_oauth"}
                    ),
                    user2.model_dump(
                        mode="json", exclude={"is_archived", "archive_date", "discord_oauth"}
                    ),
                ],
                "limit": 10,
                "offset": 0,
                "total": 2,
            }

            # Cleanup
            await company.delete()
            await user1.delete()
            await user2.delete()
            await user3.delete()

        async def test_list_users_with_results_user_role_filter(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            company_factory: Callable[[dict[str, Any]], Company],
            user_factory: Callable[[dict[str, Any]], User],
            debug: Callable[[Any], None],
        ) -> None:
            """Test list users with results."""
            # Given objects
            company = await company_factory()
            user1 = await user_factory(company_id=company.id, role=UserRole.ADMIN)
            user2 = await user_factory(company_id=company.id, role=UserRole.PLAYER)
            user3 = await user_factory(company_id=PydanticObjectId(), user_role=UserRole.ADMIN)

            # When we list users
            response = await client.get(
                build_url(UsersURL.LIST, company_id=company.id),
                headers=token_global_admin,
                params={"user_role": UserRole.ADMIN.value},
            )

            # Then we get the users
            assert response.status_code == HTTP_200_OK
            assert response.json() == {
                "items": [
                    user1.model_dump(
                        mode="json", exclude={"is_archived", "archive_date", "discord_oauth"}
                    ),
                ],
                "limit": 10,
                "offset": 0,
                "total": 1,
            }

            # Cleanup
            await company.delete()
            await user1.delete()
            await user2.delete()
            await user3.delete()

    class TestGetUser:
        """Test GetUser."""

        async def test_get_user_no_results(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
        ) -> None:
            """Test get user no results."""
            # When we get a user
            response = await client.get(
                build_url(UsersURL.DETAIL, user_id=PydanticObjectId()), headers=token_global_admin
            )
            assert response.status_code == HTTP_404_NOT_FOUND

        async def test_get_user_with_results(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            company_factory: Callable[[dict[str, Any]], Company],
            user_factory: Callable[[dict[str, Any]], User],
        ) -> None:
            """Test get user with results."""
            # Given objects
            company = await company_factory()
            user = await user_factory(company_id=company.id)
            # When we get a user
            response = await client.get(
                build_url(UsersURL.DETAIL, user_id=user.id, company_id=company.id),
                headers=token_global_admin,
            )
            assert response.status_code == HTTP_200_OK
            assert response.json() == user.model_dump(
                mode="json", exclude={"is_archived", "archive_date", "discord_oauth"}
            )

        async def test_get_user_no_results_company_federation(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            company_factory: Callable[[dict[str, Any]], Company],
            user_factory: Callable[[dict[str, Any]], User],
        ) -> None:
            """Test get user no results."""
            # Given objects
            company = await company_factory()
            user = await user_factory(company_id=company.id)
            company2 = await company_factory()

            # When we get a user
            response = await client.get(
                build_url(UsersURL.DETAIL, user_id=user.id, company_id=company2.id),
                headers=token_global_admin,
            )
            assert response.status_code == HTTP_404_NOT_FOUND

    class TestCreateUser:
        """Test CreateUser."""

        async def test_create_user_no_results(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            company_factory: Callable[[dict[str, Any]], Company],
            user_factory: Callable[[dict[str, Any]], User],
        ) -> None:
            """Test create user no results."""
            # Given objects
            company = await company_factory()
            user = await user_factory(company_id=company.id, role=UserRole.ADMIN)

            # When we create a user
            response = await client.post(
                build_url(UsersURL.CREATE, company_id=company.id),
                headers=token_global_admin,
                json={
                    "name": "Test User",
                    "email": "test@test.com",
                    "role": "ADMIN",
                    "discord_profile": {"username": "discord_username"},
                    "requesting_user_id": str(user.id),
                },
            )

            # Then we get the user
            assert response.status_code == HTTP_201_CREATED
            new_user = await User.get(response.json()["id"])
            assert response.json() == new_user.model_dump(
                mode="json", exclude={"is_archived", "archive_date", "discord_oauth"}
            )

            # Then we cleanup
            await company.delete()
            await user.delete()
            await new_user.delete()

    class TestUpdateUser:
        """Test UpdateUser."""

        async def test_update_user_no_results(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            company_factory: Callable[[dict[str, Any]], Company],
            user_factory: Callable[[dict[str, Any]], User],
        ) -> None:
            """Test update user no results."""
            # Given objects
            company = await company_factory()
            user = await user_factory(company_id=company.id, role=UserRole.ADMIN)

            # When we update a user
            response = await client.patch(
                build_url(UsersURL.UPDATE, user_id=user.id, company_id=company.id),
                headers=token_global_admin,
                json={
                    "name": "Test User Updated",
                    "email": "test@test.com",
                    "role": "ADMIN",
                    "discord_profile": {"username": "discord_username"},
                    "requesting_user_id": str(user.id),
                },
            )

            # Then we get the user
            assert response.status_code == HTTP_200_OK
            await user.sync()
            assert response.json() == user.model_dump(
                mode="json", exclude={"is_archived", "archive_date", "discord_oauth"}
            )

            assert user.name == "Test User Updated"
            assert user.email == "test@test.com"
            assert user.role == UserRole.ADMIN
            assert user.discord_profile.username == "discord_username"

            # Then we cleanup
            await company.delete()
            await user.delete()

        async def test_user_validation_error(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            company_factory: Callable[[dict[str, Any]], Company],
            user_factory: Callable[[dict[str, Any]], User],
            debug: Callable[[Any], None],
        ) -> None:
            """Test user validation error."""
            company = await company_factory()
            user = await user_factory(company_id=company.id, role=UserRole.ADMIN)

            # When we patch a user with an invalid email
            response = await client.patch(
                build_url(UsersURL.UPDATE, user_id=user.id, company_id=company.id),
                headers=token_global_admin,
                json={"email": "test", "requesting_user_id": str(user.id)},
            )
            assert response.status_code == HTTP_400_BAD_REQUEST
            # debug(response.json())
            assert response.json()["invalid_parameters"] == [
                {
                    "field": "email",
                    "message": "value is not a valid email address: An email address must have an @-sign.",
                },
            ]

    class TestDeleteUser:
        """Test DeleteUser."""

        async def test_delete_user_no_results(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            company_factory: Callable[[dict[str, Any]], Company],
            user_factory: Callable[[dict[str, Any]], User],
        ) -> None:
            """Test delete user no results."""
            # Given objects
            company = await company_factory()
            user = await user_factory(company_id=company.id, role=UserRole.ADMIN)

            # When we delete a user
            response = await client.delete(
                build_url(UsersURL.DELETE, user_id=user.id, company_id=company.id),
                headers=token_global_admin,
                params={"requesting_user_id": str(user.id)},
            )

            # Then we get the user
            assert response.status_code == HTTP_204_NO_CONTENT
            await user.sync()
            assert user.is_archived
            assert user.archive_date is not None

            await company.sync()
            assert user.id not in company.user_ids

            # Then we cleanup
            await company.delete()
            await user.delete()


class TestQuickRollController:
    """Test QuickRollController."""

    async def test_list_user_quickrolls_no_results(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_user: User,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can list quick rolls."""
        response = await client.get(build_url(UsersURL.QUICKROLLS), headers=token_company_admin)
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == []

    async def test_list_user_quickrolls_with_results(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_user: User,
        debug: Callable[[Any], None],
        quickroll_factory: Callable[[dict[str, Any]], QuickRoll],
    ) -> None:
        """Verify we can list quick rolls."""
        quickroll1 = await quickroll_factory(name="B Quick Roll 1", user_id=base_user.id)
        quickroll2 = await quickroll_factory(name="A Quick Roll 2", user_id=base_user.id)
        await quickroll_factory(name="Quick Roll 3", user_id=base_user.id, is_archived=True)
        await quickroll_factory(name="Quick Roll 4", user_id=PydanticObjectId())

        response = await client.get(build_url(UsersURL.QUICKROLLS), headers=token_company_admin)
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == [
            quickroll2.model_dump(
                mode="json",
                exclude={"is_archived", "archive_date"},
            ),
            quickroll1.model_dump(
                mode="json",
                exclude={"is_archived", "archive_date"},
            ),
        ]

    async def test_get_user_quickroll(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_user: User,
        debug: Callable[[Any], None],
        quickroll_factory: Callable[[dict[str, Any]], QuickRoll],
    ) -> None:
        """Verify we can get a quick roll."""
        quickroll = await quickroll_factory(name="Quick Roll 1", user_id=base_user.id)
        response = await client.get(
            build_url(UsersURL.QUICKROLL_DETAIL, quickroll_id=quickroll.id),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json() == quickroll.model_dump(
            mode="json",
            exclude={"is_archived", "archive_date"},
        )

    async def test_get_user_quickroll_not_found(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_user: User,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we get a 404 when getting a quick roll that doesn't exist."""
        response = await client.get(
            build_url(UsersURL.QUICKROLL_DETAIL, quickroll_id=PydanticObjectId()),
            headers=token_company_admin,
        )
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Quick roll not found"

    async def test_create_user_quickroll(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_user: User,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can create a quick roll."""
        trait = await Trait.find_one(Trait.is_archived == False)
        response = await client.post(
            build_url(UsersURL.QUICKROLL_CREATE),
            headers=token_company_admin,
            json={"name": "Quick Roll 1", "trait_ids": [str(trait.id)]},
        )
        assert response.status_code == HTTP_201_CREATED

        quickroll = await QuickRoll.get(response.json()["id"])

        assert response.json() == quickroll.model_dump(
            mode="json",
            exclude={"is_archived", "archive_date"},
        )

        assert quickroll.name == "Quick Roll 1"
        assert quickroll.user_id == base_user.id
        assert quickroll.trait_ids == [trait.id]

        await quickroll.delete()

    async def test_patch_user_quickroll(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_user: User,
        quickroll_factory: Callable[[dict[str, Any]], QuickRoll],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can patch a quick roll."""
        trait1 = await Trait.find_one(Trait.is_archived == False)
        trait2 = await Trait.find_one(Trait.is_archived == False, Trait.name != trait1.name)
        quickroll = await quickroll_factory(
            name="Quick Roll 1", user_id=base_user.id, trait_ids=[trait1.id, trait2.id]
        )

        # When we patch the quick roll
        response = await client.patch(
            build_url(UsersURL.QUICKROLL_UPDATE, quickroll_id=quickroll.id),
            headers=token_company_admin,
            json={"name": "Updated Quick Roll 2"},
        )

        # Then we get the updated quick roll
        assert response.status_code == HTTP_200_OK
        await quickroll.sync()
        assert response.json() == quickroll.model_dump(
            mode="json",
            exclude={"is_archived", "archive_date"},
        )
        assert quickroll.name == "Updated Quick Roll 2"

    async def test_delete_user_quickroll(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_user: User,
        quickroll_factory: Callable[[dict[str, Any]], QuickRoll],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify we can delete a quick roll."""
        quickroll = await quickroll_factory(name="Quick Roll 1", user_id=base_user.id)

        # When we delete the quick roll
        response = await client.delete(
            build_url(UsersURL.QUICKROLL_DELETE, quickroll_id=quickroll.id),
            headers=token_company_admin,
        )

        # Then we get the deleted quick roll
        assert response.status_code == HTTP_204_NO_CONTENT
        # Then the quick roll should be archived
        await quickroll.sync()
        assert quickroll.is_archived
        assert quickroll.archive_date is not None
