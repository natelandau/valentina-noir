"""Test user and experience controllers (Tortoise ORM)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from vapi.constants import UserRole
from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import User
from vapi.domain.urls import Users as UsersURL

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.campaign import Campaign
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.developer import Developer
    from vapi.db.sql_models.user import CampaignExperience

pytestmark = pytest.mark.anyio


class TestExperienceController:
    """Test ExperienceController."""

    async def test_get_experience_detail_no_experience(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        session_campaign: Campaign,
        user_factory: Callable[..., User],
        token_company_user: dict[str, str],
    ) -> None:
        """Verify getting experience for a user with none returns a new default record."""
        # Given a user with no campaign experience
        user = await user_factory(company=session_company)

        # When we get the experience for this user/campaign
        response = await client.get(
            build_url(
                UsersURL.EXPERIENCE_CAMPAIGN,
                user_id=user.id,
                company_id=session_company.id,
                campaign_id=session_campaign.id,
            ),
            headers=token_company_user,
        )

        # Then a default experience record is returned
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["xp_current"] == 0
        assert data["xp_total"] == 0
        assert data["cool_points"] == 0
        assert data["campaign_id"] == str(session_campaign.id)
        assert data["user_id"] == str(user.id)

    async def test_get_experience_with_experience(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        session_campaign: Campaign,
        user_factory: Callable[..., User],
        campaign_experience_factory: Callable[..., CampaignExperience],
        token_company_user: dict[str, str],
    ) -> None:
        """Verify getting experience returns existing data."""
        # Given a user with campaign experience
        user = await user_factory(company=session_company)
        experience = await campaign_experience_factory(
            user=user,
            campaign=session_campaign,
            xp_current=100,
            xp_total=200,
            cool_points=100,
        )

        # When we get the experience
        response = await client.get(
            build_url(
                UsersURL.EXPERIENCE_CAMPAIGN,
                user_id=user.id,
                company_id=session_company.id,
                campaign_id=session_campaign.id,
            ),
            headers=token_company_user,
        )

        # Then the existing experience data is returned
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["id"] == str(experience.id)
        assert data["xp_current"] == 100
        assert data["xp_total"] == 200
        assert data["cool_points"] == 100

    async def test_add_xp_to_experience(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        session_campaign: Campaign,
        session_user: User,
        user_factory: Callable[..., User],
        token_company_user: dict[str, str],
    ) -> None:
        """Verify adding XP updates campaign experience correctly."""
        # Given a user
        user = await user_factory(company=session_company)
        initial_lifetime_xp = user.lifetime_xp

        # When we add XP
        response = await client.post(
            build_url(UsersURL.XP_ADD, user_id=user.id, company_id=session_company.id),
            headers=token_company_user,
            json={
                "amount": 100,
                "requesting_user_id": str(session_user.id),
                "campaign_id": str(session_campaign.id),
            },
        )

        # Then the response contains updated experience
        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        assert data["xp_current"] == 100
        assert data["xp_total"] == 100
        assert data["cool_points"] == 0

        # Then the user's lifetime XP is updated in the database
        user = await User.get(id=user.id)
        assert user.lifetime_xp == initial_lifetime_xp + 100

    async def test_add_cp_to_experience(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        session_campaign: Campaign,
        session_user: User,
        user_factory: Callable[..., User],
        token_company_user: dict[str, str],
    ) -> None:
        """Verify adding cool points updates campaign experience correctly."""
        # Given a user
        user = await user_factory(company=session_company)
        initial_lifetime_cp = user.lifetime_cool_points

        # When we add CP
        response = await client.post(
            build_url(UsersURL.CP_ADD, user_id=user.id, company_id=session_company.id),
            headers=token_company_user,
            json={
                "amount": 1,
                "requesting_user_id": str(session_user.id),
                "campaign_id": str(session_campaign.id),
            },
        )

        # Then the response contains updated experience
        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        assert data["xp_current"] == 10
        assert data["xp_total"] == 10
        assert data["cool_points"] == 1

        # Then the user's lifetime cool points are updated in the database
        user = await User.get(id=user.id)
        assert user.lifetime_cool_points == initial_lifetime_cp + 1

    async def test_remove_xp_from_experience(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        session_company: Company,
        session_company_user: Developer,
        session_campaign: Campaign,
        session_user: User,
        user_factory: Callable[..., User],
        campaign_experience_factory: Callable[..., CampaignExperience],
        token_company_user: dict[str, str],
    ) -> None:
        """Verify removing XP updates campaign experience correctly."""
        # Given a user with existing experience
        user = await user_factory(company=session_company)
        await campaign_experience_factory(
            user=user,
            campaign=session_campaign,
            xp_current=10,
            xp_total=10,
            cool_points=1,
        )

        # When we remove XP
        response = await client.post(
            build_url(UsersURL.XP_REMOVE, user_id=user.id, company_id=session_company.id),
            headers=token_company_user,
            json={
                "amount": 6,
                "requesting_user_id": str(session_user.id),
                "campaign_id": str(session_campaign.id),
            },
        )

        # Then the response contains updated experience
        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        assert data["xp_current"] == 4
        assert data["xp_total"] == 10
        assert data["cool_points"] == 1


class TestUserController:
    """Test UserController."""

    class TestListUsers:
        """Test ListUsers."""

        async def test_list_users_no_results(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            company_factory: Callable[..., Company],
        ) -> None:
            """Verify listing users returns empty when none exist."""
            # Given a company with no users
            company = await company_factory(name="empty-co", email="empty@test.com")

            # When we list users
            response = await client.get(
                build_url(UsersURL.LIST, company_id=company.id), headers=token_global_admin
            )

            # Then we get no users
            assert response.status_code == HTTP_200_OK
            assert response.json() == {"items": [], "limit": 10, "offset": 0, "total": 0}

        async def test_list_users_with_results(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            user_factory: Callable[..., User],
        ) -> None:
            """Verify listing users returns paginated results."""
            # Given users in the company
            user1 = await user_factory(company=session_company, role="ADMIN")
            user2 = await user_factory(company=session_company, role="PLAYER")

            # When we list users
            response = await client.get(
                build_url(UsersURL.LIST, company_id=session_company.id),
                headers=token_global_admin,
            )

            # Then we get the users
            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert data["total"] >= 2
            returned_ids = {item["id"] for item in data["items"]}
            assert str(user1.id) in returned_ids
            assert str(user2.id) in returned_ids

        async def test_list_users_with_results_user_role_filter(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            user_factory: Callable[..., User],
        ) -> None:
            """Verify listing users filtered by role returns only matching users."""
            # Given users with different roles
            admin_user = await user_factory(company=session_company, role="ADMIN")
            await user_factory(company=session_company, role="PLAYER")

            # When we list users filtered by ADMIN role
            response = await client.get(
                build_url(UsersURL.LIST, company_id=session_company.id),
                headers=token_global_admin,
                params={"user_role": UserRole.ADMIN.value},
            )

            # Then the admin user is returned
            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert data["total"] >= 1
            returned_ids = {item["id"] for item in data["items"]}
            assert str(admin_user.id) in returned_ids

    class TestGetUser:
        """Test GetUser."""

        async def test_get_user_no_results(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
        ) -> None:
            """Verify getting a non-existent user returns 404."""
            # When we get a user that does not exist
            response = await client.get(
                build_url(UsersURL.DETAIL, user_id=uuid4(), company_id=session_company.id),
                headers=token_global_admin,
            )

            # Then we get a 404
            assert response.status_code == HTTP_404_NOT_FOUND

        async def test_get_user_with_results(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            user_factory: Callable[..., User],
        ) -> None:
            """Verify getting a user returns correct data."""
            # Given a user
            user = await user_factory(company=session_company)

            # When we get the user
            response = await client.get(
                build_url(UsersURL.DETAIL, user_id=user.id, company_id=session_company.id),
                headers=token_global_admin,
            )

            # Then the response contains correct user data
            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert data["id"] == str(user.id)
            assert data["username"] == user.username
            assert data["email"] == user.email
            assert data["company_id"] == str(session_company.id)

        async def test_get_user_no_results_company_federation(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            user_factory: Callable[..., User],
            company_factory: Callable[..., Company],
        ) -> None:
            """Verify getting a user from wrong company returns 404."""
            # Given a user in one company
            user = await user_factory(company=session_company)
            company2 = await company_factory(name="other-co", email="other@test.com")

            # When we try to get the user from a different company
            response = await client.get(
                build_url(UsersURL.DETAIL, user_id=user.id, company_id=company2.id),
                headers=token_global_admin,
            )

            # Then we get 404
            assert response.status_code == HTTP_404_NOT_FOUND

        async def test_get_user_no_include_omits_children(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user: User,
        ) -> None:
            """Verify getUser without include omits child resource keys."""
            # Given an existing session user
            # When we get the user without include
            response = await client.get(
                build_url(
                    UsersURL.DETAIL,
                    user_id=session_user.id,
                    company_id=session_company.id,
                ),
                headers=token_global_admin,
            )

            # Then the response has no child keys
            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert data["id"] == str(session_user.id)
            assert "quickrolls" not in data
            assert "notes" not in data
            assert "assets" not in data
            assert "characters" not in data

        async def test_get_user_include_all_children(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user: User,
            session_campaign: Campaign,
            quickroll_factory: Callable[..., Any],
            note_factory: Callable[..., Any],
            s3asset_factory: Callable[..., Any],
            character_factory: Callable[..., Any],
        ) -> None:
            """Verify getUser with all includes embeds each child list."""
            # Given one of each child attached to the session user
            quickroll = await quickroll_factory(user=session_user)
            note = await note_factory(company=session_company, user=session_user)
            asset = await s3asset_factory(
                company=session_company,
                user_parent=session_user,
                uploaded_by=session_user,
            )
            character = await character_factory(
                company=session_company,
                user_player=session_user,
                user_creator=session_user,
                campaign=session_campaign,
            )

            # When we include all child types
            response = await client.get(
                build_url(
                    UsersURL.DETAIL,
                    user_id=session_user.id,
                    company_id=session_company.id,
                ),
                headers=token_global_admin,
                params={"include": ["quickrolls", "notes", "assets", "characters"]},
            )

            # Then each child list is present with the created item
            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert len(data["quickrolls"]) == 1
            assert data["quickrolls"][0]["id"] == str(quickroll.id)
            assert len(data["notes"]) == 1
            assert data["notes"][0]["id"] == str(note.id)
            assert len(data["assets"]) == 1
            assert data["assets"][0]["id"] == str(asset.id)
            assert len(data["characters"]) == 1
            assert data["characters"][0]["id"] == str(character.id)

        async def test_get_user_include_characters_only_played(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user: User,
            session_campaign: Campaign,
            user_factory: Callable[..., User],
            character_factory: Callable[..., Any],
        ) -> None:
            """Verify include=characters returns only played characters, not created."""
            # Given two characters: one played by session user and one only created by them
            other_user = await user_factory(company=session_company)
            played = await character_factory(
                company=session_company,
                user_player=session_user,
                user_creator=session_user,
                campaign=session_campaign,
            )
            await character_factory(
                company=session_company,
                user_player=other_user,
                user_creator=session_user,
                campaign=session_campaign,
            )

            # When we include characters
            response = await client.get(
                build_url(
                    UsersURL.DETAIL,
                    user_id=session_user.id,
                    company_id=session_company.id,
                ),
                headers=token_global_admin,
                params={"include": ["characters"]},
            )

            # Then only the played character is returned
            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert len(data["characters"]) == 1
            assert data["characters"][0]["id"] == str(played.id)

        async def test_get_user_include_characters_excludes_archived(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user: User,
            session_campaign: Campaign,
            character_factory: Callable[..., Any],
        ) -> None:
            """Verify include=characters excludes archived characters from the embedded list."""
            # Given an active and an archived character played by the session user
            active = await character_factory(
                company=session_company,
                user_player=session_user,
                user_creator=session_user,
                campaign=session_campaign,
            )
            archived = await character_factory(
                company=session_company,
                user_player=session_user,
                user_creator=session_user,
                campaign=session_campaign,
            )
            archived.is_archived = True
            await archived.save()

            # When we include characters
            response = await client.get(
                build_url(
                    UsersURL.DETAIL,
                    user_id=session_user.id,
                    company_id=session_company.id,
                ),
                headers=token_global_admin,
                params={"include": ["characters"]},
            )

            # Then only the active character is returned
            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert len(data["characters"]) == 1
            assert data["characters"][0]["id"] == str(active.id)

        async def test_get_user_include_quickrolls_excludes_archived(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user: User,
            quickroll_factory: Callable[..., Any],
        ) -> None:
            """Verify include=quickrolls excludes archived quick rolls from the embedded list."""
            # Given an active and an archived quick roll on the session user
            active = await quickroll_factory(user=session_user)
            archived = await quickroll_factory(user=session_user)
            archived.is_archived = True
            await archived.save()

            # When we include quickrolls
            response = await client.get(
                build_url(
                    UsersURL.DETAIL,
                    user_id=session_user.id,
                    company_id=session_company.id,
                ),
                headers=token_global_admin,
                params={"include": ["quickrolls"]},
            )

            # Then only the active quick roll is returned
            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert len(data["quickrolls"]) == 1
            assert data["quickrolls"][0]["id"] == str(active.id)

        async def test_get_user_include_notes_excludes_archived(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user: User,
            note_factory: Callable[..., Any],
        ) -> None:
            """Verify include=notes excludes archived notes from the embedded list."""
            # Given an active and an archived note on the session user
            active = await note_factory(company=session_company, user=session_user)
            archived = await note_factory(company=session_company, user=session_user)
            archived.is_archived = True
            await archived.save()

            # When we include notes
            response = await client.get(
                build_url(
                    UsersURL.DETAIL,
                    user_id=session_user.id,
                    company_id=session_company.id,
                ),
                headers=token_global_admin,
                params={"include": ["notes"]},
            )

            # Then only the active note is returned
            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert len(data["notes"]) == 1
            assert data["notes"][0]["id"] == str(active.id)

        async def test_get_user_include_assets_excludes_archived(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user: User,
            s3asset_factory: Callable[..., Any],
        ) -> None:
            """Verify include=assets excludes archived owned assets from the embedded list."""
            # Given an active and an archived asset owned by the session user
            active = await s3asset_factory(
                company=session_company,
                user_parent=session_user,
                uploaded_by=session_user,
            )
            archived = await s3asset_factory(
                company=session_company,
                user_parent=session_user,
                uploaded_by=session_user,
            )
            archived.is_archived = True
            await archived.save()

            # When we include assets
            response = await client.get(
                build_url(
                    UsersURL.DETAIL,
                    user_id=session_user.id,
                    company_id=session_company.id,
                ),
                headers=token_global_admin,
                params={"include": ["assets"]},
            )

            # Then only the active asset is returned
            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert len(data["assets"]) == 1
            assert data["assets"][0]["id"] == str(active.id)

        async def test_get_user_include_invalid_value(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user: User,
        ) -> None:
            """Verify invalid include value returns 400."""
            # When we pass an invalid include value
            response = await client.get(
                build_url(
                    UsersURL.DETAIL,
                    user_id=session_user.id,
                    company_id=session_company.id,
                ),
                headers=token_global_admin,
                params={"include": ["bogus"]},
            )

            # Then we get 400
            assert response.status_code == HTTP_400_BAD_REQUEST

    class TestCreateUser:
        """Test CreateUser."""

        async def test_create_user(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user_admin: User,
        ) -> None:
            """Verify creating a user returns the new user."""
            # When we create a user
            response = await client.post(
                build_url(UsersURL.CREATE, company_id=session_company.id),
                headers=token_global_admin,
                json={
                    "name_first": "Test",
                    "name_last": "User",
                    "username": "test_user",
                    "email": "test@test.com",
                    "role": "ADMIN",
                    "discord_profile": {"username": "discord_username"},
                    "requesting_user_id": str(session_user_admin.id),
                },
            )

            # Then the user is created
            assert response.status_code == HTTP_201_CREATED
            data = response.json()
            assert data["username"] == "test_user"
            assert data["email"] == "test@test.com"
            assert data["role"] == "ADMIN"
            assert data["company_id"] == str(session_company.id)

            # Then the user exists in the database
            new_user = await User.get(id=data["id"])
            assert new_user is not None
            assert new_user.username == "test_user"

    class TestUpdateUser:
        """Test UpdateUser."""

        async def test_update_user(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            user_factory: Callable[..., User],
        ) -> None:
            """Verify updating a user returns the updated data."""
            # Given a user
            user = await user_factory(company=session_company, role="ADMIN")

            # When we update the user
            response = await client.patch(
                build_url(UsersURL.UPDATE, user_id=user.id, company_id=session_company.id),
                headers=token_global_admin,
                json={
                    "name_first": "Test",
                    "name_last": "User",
                    "username": "test_user_updated",
                    "email": "test@test.com",
                    "role": "ADMIN",
                    "discord_profile": {"username": "discord_username"},
                    "requesting_user_id": str(user.id),
                },
            )

            # Then the response shows updated data
            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert data["name_first"] == "Test"
            assert data["name_last"] == "User"
            assert data["username"] == "test_user_updated"
            assert data["email"] == "test@test.com"
            assert data["role"] == "ADMIN"
            assert data["discord_profile"]["username"] == "discord_username"

            # Then the database is updated
            user = await User.get(id=user.id)
            assert user.username == "test_user_updated"

    class TestDeleteUser:
        """Test DeleteUser."""

        async def test_delete_user(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            user_factory: Callable[..., User],
        ) -> None:
            """Verify deleting a user archives them."""
            # Given a user
            user = await user_factory(company=session_company, role="ADMIN")

            # When we delete the user
            response = await client.delete(
                build_url(UsersURL.DELETE, user_id=user.id, company_id=session_company.id),
                headers=token_global_admin,
                params={"requesting_user_id": str(user.id)},
            )

            # Then the user is deleted
            assert response.status_code == HTTP_204_NO_CONTENT

            # Then the user is archived in the database
            user = await User.get(id=user.id)
            assert user.is_archived is True
            assert user.archive_date is not None


class TestQuickRollController:
    """Test QuickRollController."""

    async def test_list_user_quickrolls_no_results(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_user: dict[str, str],
        session_company: Company,
        session_company_user: Developer,
        session_user: User,
    ) -> None:
        """Verify listing quick rolls returns empty when none exist."""
        response = await client.get(
            build_url(
                UsersURL.QUICKROLLS,
                company_id=session_company.id,
                user_id=session_user.id,
            ),
            headers=token_company_user,
        )
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == []

    async def test_list_user_quickrolls_with_results(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_user: dict[str, str],
        session_company: Company,
        session_company_user: Developer,
        session_user: User,
        quickroll_factory: Callable[..., QuickRoll],
    ) -> None:
        """Verify listing quick rolls returns sorted, non-archived results."""
        # Given two active quick rolls and one archived
        traits = await Trait.filter(is_archived=False).limit(2)
        qr1 = await quickroll_factory(name="B Quick Roll", user=session_user, traits=traits)
        qr2 = await quickroll_factory(name="A Quick Roll", user=session_user, traits=traits)
        await quickroll_factory(name="Archived Roll", user=session_user, is_archived=True)

        # When we list quick rolls
        response = await client.get(
            build_url(
                UsersURL.QUICKROLLS,
                company_id=session_company.id,
                user_id=session_user.id,
            ),
            headers=token_company_user,
        )

        # Then only active quick rolls are returned, sorted by name
        assert response.status_code == HTTP_200_OK
        items = response.json()["items"]
        assert len(items) == 2
        assert items[0]["name"] == "A Quick Roll"
        assert items[1]["name"] == "B Quick Roll"
        assert items[0]["id"] == str(qr2.id)
        assert items[1]["id"] == str(qr1.id)

    async def test_get_user_quickroll(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_user: dict[str, str],
        session_company: Company,
        session_company_user: Developer,
        session_user: User,
        quickroll_factory: Callable[..., QuickRoll],
    ) -> None:
        """Verify getting a quick roll by ID returns correct data."""
        traits = await Trait.filter(is_archived=False).limit(1)
        quickroll = await quickroll_factory(name="Quick Roll 1", user=session_user, traits=traits)

        response = await client.get(
            build_url(
                UsersURL.QUICKROLL_DETAIL,
                company_id=session_company.id,
                user_id=session_user.id,
                quickroll_id=quickroll.id,
            ),
            headers=token_company_user,
        )
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["id"] == str(quickroll.id)
        assert data["name"] == "Quick Roll 1"
        assert data["trait_ids"] == [str(t.id) for t in traits]

    async def test_get_user_quickroll_not_found(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_user: dict[str, str],
        session_company: Company,
        session_company_user: Developer,
        session_user: User,
    ) -> None:
        """Verify getting a non-existent quick roll returns 404."""
        response = await client.get(
            build_url(
                UsersURL.QUICKROLL_DETAIL,
                company_id=session_company.id,
                user_id=session_user.id,
                quickroll_id=uuid4(),
            ),
            headers=token_company_user,
        )
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Quick roll not found"

    async def test_create_user_quickroll(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_user: dict[str, str],
        session_company: Company,
        session_company_user: Developer,
        session_user: User,
    ) -> None:
        """Verify creating a quick roll returns the new resource."""
        trait = await Trait.filter(is_archived=False).first()
        response = await client.post(
            build_url(
                UsersURL.QUICKROLL_CREATE,
                company_id=session_company.id,
                user_id=session_user.id,
            ),
            headers=token_company_user,
            json={"name": "Quick Roll 1", "trait_ids": [str(trait.id)]},
        )
        assert response.status_code == HTTP_201_CREATED
        data = response.json()

        assert data["name"] == "Quick Roll 1"
        assert data["user_id"] == str(session_user.id)
        assert data["trait_ids"] == [str(trait.id)]

        # Verify persisted in database
        quickroll = await QuickRoll.get(id=data["id"]).prefetch_related("traits")
        assert quickroll.name == "Quick Roll 1"
        assert [t.id for t in quickroll.traits] == [trait.id]

    async def test_patch_user_quickroll(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_user: dict[str, str],
        session_company: Company,
        session_company_user: Developer,
        session_user: User,
        quickroll_factory: Callable[..., QuickRoll],
    ) -> None:
        """Verify patching a quick roll updates only sent fields."""
        traits = await Trait.filter(is_archived=False).limit(2)
        quickroll = await quickroll_factory(name="Quick Roll 1", user=session_user, traits=traits)

        # When we patch the name only
        response = await client.patch(
            build_url(
                UsersURL.QUICKROLL_UPDATE,
                company_id=session_company.id,
                user_id=session_user.id,
                quickroll_id=quickroll.id,
            ),
            headers=token_company_user,
            json={"name": "Updated Quick Roll"},
        )

        # Then the name is updated, traits remain
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["name"] == "Updated Quick Roll"
        assert len(data["trait_ids"]) == 2

    async def test_patch_user_quickroll_with_traits(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_user: dict[str, str],
        session_company: Company,
        session_company_user: Developer,
        session_user: User,
        quickroll_factory: Callable[..., QuickRoll],
    ) -> None:
        """Verify patching a quick roll with new trait_ids replaces existing traits."""
        # Given a quickroll with 2 traits
        initial_traits = await Trait.filter(is_archived=False).limit(2)
        quickroll = await quickroll_factory(
            name="Quick Roll 1", user=session_user, traits=initial_traits
        )

        # Given a different set of traits to replace them
        replacement_traits = await Trait.filter(is_archived=False).offset(2).limit(3)
        replacement_ids = [str(t.id) for t in replacement_traits]

        # When we patch with new trait_ids and description
        response = await client.patch(
            build_url(
                UsersURL.QUICKROLL_UPDATE,
                company_id=session_company.id,
                user_id=session_user.id,
                quickroll_id=quickroll.id,
            ),
            headers=token_company_user,
            json={
                "description": "Updated description",
                "trait_ids": replacement_ids,
            },
        )

        # Then the traits and description are updated, name unchanged
        assert response.status_code == HTTP_200_OK
        data = response.json()
        assert data["name"] == "Quick Roll 1"
        assert data["description"] == "Updated description"
        assert len(data["trait_ids"]) == 3
        assert set(data["trait_ids"]) == {str(t.id) for t in replacement_traits}

    async def test_delete_user_quickroll(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_user: dict[str, str],
        session_company: Company,
        session_company_user: Developer,
        session_user: User,
        quickroll_factory: Callable[..., QuickRoll],
    ) -> None:
        """Verify deleting a quick roll archives it."""
        quickroll = await quickroll_factory(name="Quick Roll 1", user=session_user)

        response = await client.delete(
            build_url(
                UsersURL.QUICKROLL_DELETE,
                company_id=session_company.id,
                user_id=session_user.id,
                quickroll_id=quickroll.id,
            ),
            headers=token_company_user,
        )

        assert response.status_code == HTTP_204_NO_CONTENT

        # Verify the quick roll is archived
        archived = await QuickRoll.get(id=quickroll.id)
        assert archived.is_archived
        assert archived.archive_date is not None


class TestUnapprovedUserController:
    """Test UnapprovedUserController."""

    class TestListUnapprovedUsers:
        """Test list unapproved users."""

        async def test_list_unapproved_users_no_results(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user_admin: User,
        ) -> None:
            """Verify listing unapproved users returns empty when none exist."""
            # When we list unapproved users
            response = await client.get(
                build_url(UsersURL.UNAPPROVED_LIST, company_id=session_company.id),
                headers=token_global_admin,
                params={"requesting_user_id": str(session_user_admin.id)},
            )

            # Then we get an empty paginated response
            assert response.status_code == HTTP_200_OK
            assert response.json() == {"items": [], "limit": 10, "offset": 0, "total": 0}

        async def test_list_unapproved_users_with_results(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user_admin: User,
            user_factory: Callable[..., User],
        ) -> None:
            """Verify listing unapproved users returns only unapproved, non-archived users."""
            # Given unapproved and approved users
            unapproved_user = await user_factory(company=session_company, role="UNAPPROVED")
            await user_factory(company=session_company, role="PLAYER")

            # When we list unapproved users
            response = await client.get(
                build_url(UsersURL.UNAPPROVED_LIST, company_id=session_company.id),
                headers=token_global_admin,
                params={"requesting_user_id": str(session_user_admin.id)},
            )

            # Then we get only the unapproved, non-archived user
            assert response.status_code == HTTP_200_OK
            data = response.json()
            assert data["total"] == 1
            assert len(data["items"]) == 1
            assert data["items"][0]["id"] == str(unapproved_user.id)

    class TestApproveUser:
        """Test approve user."""

        async def test_approve_user_success(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user_admin: User,
            user_factory: Callable[..., User],
        ) -> None:
            """Verify approving an unapproved user sets the new role."""
            # Given an unapproved user
            unapproved_user = await user_factory(company=session_company, role="UNAPPROVED")

            # When we approve the user
            response = await client.post(
                build_url(
                    UsersURL.APPROVE,
                    user_id=unapproved_user.id,
                    company_id=session_company.id,
                ),
                headers=token_global_admin,
                json={
                    "role": UserRole.PLAYER.value,
                    "requesting_user_id": str(session_user_admin.id),
                },
            )

            # Then the user is approved
            assert response.status_code == HTTP_201_CREATED
            assert response.json()["role"] == UserRole.PLAYER.value

            # Then the database is updated
            updated_user = await User.get(id=unapproved_user.id)
            assert updated_user.role == UserRole.PLAYER

        async def test_approve_user_not_unapproved(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user_admin: User,
            user_factory: Callable[..., User],
        ) -> None:
            """Verify approving a non-unapproved user returns 400."""
            # Given a player user
            player_user = await user_factory(company=session_company, role="PLAYER")

            # When we try to approve a non-unapproved user
            response = await client.post(
                build_url(
                    UsersURL.APPROVE,
                    user_id=player_user.id,
                    company_id=session_company.id,
                ),
                headers=token_global_admin,
                json={
                    "role": UserRole.STORYTELLER.value,
                    "requesting_user_id": str(session_user_admin.id),
                },
            )

            # Then we get a validation error
            assert response.status_code == HTTP_400_BAD_REQUEST

    class TestDenyUser:
        """Test deny user."""

        async def test_deny_user_success(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user_admin: User,
            user_factory: Callable[..., User],
        ) -> None:
            """Verify denying an unapproved user archives them."""
            # Given an unapproved user
            unapproved_user = await user_factory(company=session_company, role="UNAPPROVED")

            # When we deny the user
            response = await client.post(
                build_url(
                    UsersURL.DENY,
                    user_id=unapproved_user.id,
                    company_id=session_company.id,
                ),
                headers=token_global_admin,
                json={
                    "requesting_user_id": str(session_user_admin.id),
                },
            )

            # Then the response is successful
            assert response.status_code == HTTP_201_CREATED

            # Then the user is archived
            updated_user = await User.get(id=unapproved_user.id)
            assert updated_user.is_archived is True

        async def test_deny_user_not_unapproved(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            session_user_admin: User,
            user_factory: Callable[..., User],
        ) -> None:
            """Verify denying a non-unapproved user returns 400."""
            # Given a player user
            player_user = await user_factory(company=session_company, role="PLAYER")

            # When we try to deny a non-unapproved user
            response = await client.post(
                build_url(
                    UsersURL.DENY,
                    user_id=player_user.id,
                    company_id=session_company.id,
                ),
                headers=token_global_admin,
                json={
                    "requesting_user_id": str(session_user_admin.id),
                },
            )

            # Then we get a validation error
            assert response.status_code == HTTP_400_BAD_REQUEST


class TestUserRegistration:
    """Test user registration and merge endpoints."""

    class TestRegisterUser:
        """Test RegisterUser."""

        async def test_register_user_success(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
        ) -> None:
            """Verify registering a user creates an UNAPPROVED user."""
            # When we register a user
            response = await client.post(
                build_url(UsersURL.REGISTER, company_id=session_company.id),
                headers=token_global_admin,
                json={
                    "username": "sso_user",
                    "email": "sso@example.com",
                    "google_profile": {
                        "email": "sso@gmail.com",
                        "username": "SSO User",
                    },
                },
            )

            # Then the user is created with UNAPPROVED role
            assert response.status_code == HTTP_201_CREATED
            result = response.json()
            assert result["role"] == "UNAPPROVED"
            assert result["username"] == "sso_user"
            assert result["email"] == "sso@example.com"
            assert result["google_profile"]["email"] == "sso@gmail.com"

            # Then the user exists in the database
            new_user = await User.get(id=result["id"])
            assert new_user is not None
            assert new_user.role == UserRole.UNAPPROVED

        async def test_register_user_missing_required_fields(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
        ) -> None:
            """Verify registration fails without required fields."""
            # When we register without required fields
            response = await client.post(
                build_url(UsersURL.REGISTER, company_id=session_company.id),
                headers=token_global_admin,
                json={"name_first": "Test"},
            )

            # Then validation fails
            assert response.status_code == HTTP_400_BAD_REQUEST

    class TestMergeUsers:
        """Test MergeUsers."""

        async def test_merge_users_success(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            user_factory: Callable[..., User],
        ) -> None:
            """Verify merging absorbs profile and deletes secondary."""
            # Given a primary user and an UNAPPROVED secondary user
            admin_user = await user_factory(company=session_company, role="ADMIN")
            primary_user = await user_factory(
                company=session_company,
                google_profile=None,
                github_profile=None,
                discord_profile=None,
            )
            secondary_user = await user_factory(
                company=session_company,
                role="UNAPPROVED",
                google_profile={"email": "secondary@gmail.com", "username": "Secondary"},
            )

            # When we merge the users
            response = await client.post(
                build_url(UsersURL.MERGE, company_id=session_company.id),
                headers=token_global_admin,
                json={
                    "primary_user_id": str(primary_user.id),
                    "secondary_user_id": str(secondary_user.id),
                    "requesting_user_id": str(admin_user.id),
                },
            )

            # Then the merge succeeds
            assert response.status_code == HTTP_201_CREATED
            result = response.json()
            assert result["id"] == str(primary_user.id)
            assert result["google_profile"]["email"] == "secondary@gmail.com"

            # Then the secondary user is archived
            archived_user = await User.get(id=secondary_user.id)
            assert archived_user.is_archived is True

        async def test_merge_users_secondary_not_unapproved(
            self,
            client: AsyncClient,
            build_url: Callable[[str, Any], str],
            token_global_admin: dict[str, str],
            session_company: Company,
            session_global_admin: Developer,
            user_factory: Callable[..., User],
        ) -> None:
            """Verify merge rejects when secondary is not UNAPPROVED."""
            # Given two active users
            admin_user = await user_factory(company=session_company, role="ADMIN")
            primary_user = await user_factory(company=session_company)
            secondary_user = await user_factory(company=session_company, role="PLAYER")

            # When we attempt to merge
            response = await client.post(
                build_url(UsersURL.MERGE, company_id=session_company.id),
                headers=token_global_admin,
                json={
                    "primary_user_id": str(primary_user.id),
                    "secondary_user_id": str(secondary_user.id),
                    "requesting_user_id": str(admin_user.id),
                },
            )

            # Then the merge is rejected
            assert response.status_code == HTTP_400_BAD_REQUEST


class TestListUsersEmailFilter:
    """Test email filter on list users endpoint."""

    async def test_list_users_email_filter(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        user_factory: Callable[..., User],
    ) -> None:
        """Verify filtering users by email returns matching results."""
        # Given users with different emails
        await user_factory(company=session_company, email="alice@example.com", username="alice")
        await user_factory(company=session_company, email="bob@example.com", username="bob")

        # When we filter by email
        response = await client.get(
            build_url(UsersURL.LIST, company_id=session_company.id),
            headers=token_global_admin,
            params={"email": "alice@example.com"},
        )

        # Then only the matching user is returned
        assert response.status_code == HTTP_200_OK
        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["email"] == "alice@example.com"

    async def test_list_users_email_filter_no_results(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
    ) -> None:
        """Verify email filter returns empty when no match."""
        # When we filter by a nonexistent email
        response = await client.get(
            build_url(UsersURL.LIST, company_id=session_company.id),
            headers=token_global_admin,
            params={"email": "nonexistent@example.com"},
        )

        # Then an empty list is returned
        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == []
