"""Unit tests for user services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from uuid_utils import uuid7

from vapi.constants import PermissionsGrantXP, UserRole
from vapi.db.models import QuickRoll, Trait
from vapi.db.sql_models.company import Company, CompanySettings
from vapi.db.sql_models.user import CampaignExperience, User
from vapi.domain.controllers.user.dto import UserCreate, UserPatch, UserRegister
from vapi.domain.services import UserQuickRollService, UserService, UserXPService
from vapi.lib.exceptions import NotEnoughXPError, PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.models import User as BeanieUser
    from vapi.db.sql_models.campaign import Campaign

pytestmark = pytest.mark.anyio


class TestUserService:
    """Test the user service."""

    async def test_validate_user_can_manage_user_self(
        self,
        pg_user_factory: Callable[..., User],
        pg_company_factory: Callable[..., Company],
        debug: Callable[..., None],
    ) -> None:
        """Verify a user can manage themselves."""
        # Given a user
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)

        # When we validate the user can manage themselves
        service = UserService()
        await service.validate_user_can_manage_user(
            requesting_user_id=user.id,
            user_to_manage_id=user.id,
        )

        # Then no exception is raised
        assert True

    async def test_validate_user_can_manage_user_admin_user(
        self,
        pg_user_factory: Callable[..., User],
        pg_company_factory: Callable[..., Company],
        debug: Callable[..., None],
    ) -> None:
        """Verify an admin can manage another user."""
        # Given an admin and a target user
        company = await pg_company_factory()
        target_user = await pg_user_factory(company=company)
        requesting_user = await pg_user_factory(role=UserRole.ADMIN, company=company)

        # When we validate the admin can manage the target user
        service = UserService()
        await service.validate_user_can_manage_user(
            requesting_user_id=requesting_user.id,
            user_to_manage_id=target_user.id,
        )

        # Then no exception is raised
        assert True

    async def test_validate_user_can_manage_user_player_user(
        self,
        pg_user_factory: Callable[..., User],
        pg_company_factory: Callable[..., Company],
        debug: Callable[..., None],
    ) -> None:
        """Verify a player cannot manage another user."""
        # Given a player and a target user
        company = await pg_company_factory()
        target_user = await pg_user_factory(company=company)
        requesting_user = await pg_user_factory(role=UserRole.PLAYER, company=company)

        # When we validate the player can manage the target user
        # Then a PermissionDeniedError is raised
        service = UserService()
        with pytest.raises(PermissionDeniedError, match="not authorized to manage this user"):
            await service.validate_user_can_manage_user(
                requesting_user_id=requesting_user.id,
                user_to_manage_id=target_user.id,
            )

    async def test_validate_user_can_manage_user_user_not_found(
        self,
        pg_user_factory: Callable[..., User],
        pg_company_factory: Callable[..., Company],
        debug: Callable[..., None],
    ) -> None:
        """Verify managing a user with a non-existent requesting user raises ValidationError."""
        # Given a target user and a non-existent requesting user ID
        company = await pg_company_factory()
        target_user = await pg_user_factory(company=company)

        # When we validate with a non-existent requesting user
        # Then a ValidationError is raised
        service = UserService()
        with pytest.raises(ValidationError, match=r"User .* not found"):
            await service.validate_user_can_manage_user(
                requesting_user_id=uuid7(),
                user_to_manage_id=target_user.id,
            )

    async def test_create_user_success(
        self,
        pg_company_factory: Callable[..., Company],
        pg_user_factory: Callable[..., User],
        mocker: Any,
        debug: Callable[..., None],
    ) -> None:
        """Verify creating a user succeeds with valid data."""
        # Given a company and an admin requesting user
        company = await pg_company_factory()
        requesting_user = await pg_user_factory(role=UserRole.ADMIN, company=company)
        data = UserCreate(
            name_first="Test",
            name_last="User",
            username="test_user",
            email="test@example.com",
            role="PLAYER",
            discord_profile={"global_name": "global name"},
            google_profile={"email": "test@gmail.com", "username": "Test User"},
            github_profile={"login": "testuser", "email": "test@github.com"},
            requesting_user_id=requesting_user.id,
        )
        spy = mocker.spy(UserService, "validate_user_can_manage_user")

        # When we create the user
        service = UserService()
        new_user = await service.create_user(company=company, data=data)

        # Then the user is created with correct attributes
        assert new_user.name_first == "Test"
        assert new_user.name_last == "User"
        assert new_user.username == "test_user"
        assert new_user.email == "test@example.com"
        assert new_user.role == UserRole.PLAYER
        assert new_user.discord_profile["global_name"] == "global name"
        assert new_user.google_profile["email"] == "test@gmail.com"
        assert new_user.google_profile["username"] == "Test User"
        assert new_user.github_profile["login"] == "testuser"
        assert new_user.github_profile["email"] == "test@github.com"
        assert new_user.company_id == company.id
        spy.assert_called_once()

    async def test_update_user_success(
        self,
        pg_user_factory: Callable[..., User],
        pg_company_factory: Callable[..., Company],
        mocker: Any,
        debug: Callable[..., None],
    ) -> None:
        """Verify updating a user succeeds with valid patch data."""
        # Given an existing user with profile data
        spy = mocker.spy(UserService, "validate_user_can_manage_user")
        company = await pg_company_factory()
        target_user = await pg_user_factory(
            name_first="Test",
            name_last="User",
            username="test_user",
            email="test@example.com",
            role=UserRole.PLAYER,
            company=company,
            discord_profile={"id": "1234567890", "global_name": "global name"},
            google_profile={"id": "google123", "email": "test@gmail.com"},
            github_profile={"id": "583231", "login": "testuser"},
        )

        data = UserPatch(
            name_first="update",
            discord_profile={"global_name": "global name updated"},
            google_profile={"username": "Updated Google User"},
            github_profile={"username": "Updated GitHub User"},
            requesting_user_id=target_user.id,
        )

        # When we update the user
        service = UserService()
        updated_user = await service.update_user(user=target_user, data=data)

        # Then the user is updated with new values and unchanged fields preserved
        assert updated_user.name_first == "update"
        assert updated_user.name_last == "User"
        assert updated_user.username == "test_user"
        assert updated_user.email == "test@example.com"
        assert updated_user.role == UserRole.PLAYER
        assert updated_user.discord_profile["global_name"] == "global name updated"
        assert updated_user.google_profile["username"] == "Updated Google User"
        assert updated_user.github_profile["username"] == "Updated GitHub User"
        assert updated_user.company_id == company.id
        spy.assert_called_once()

    async def test_approve_user_success(
        self,
        pg_user_factory: Callable[..., User],
        pg_company_factory: Callable[..., Company],
        debug: Callable[..., None],
    ) -> None:
        """Verify approving an unapproved user sets the new role."""
        # Given an unapproved user and an admin
        company = await pg_company_factory()
        admin_user = await pg_user_factory(role=UserRole.ADMIN, company=company)
        unapproved_user = await pg_user_factory(role=UserRole.UNAPPROVED, company=company)

        # When we approve the user
        service = UserService()
        result = await service.approve_user(
            user=unapproved_user,
            role=UserRole.PLAYER,
            requesting_user_id=admin_user.id,
        )

        # Then the user role is updated
        assert result.role == UserRole.PLAYER

    async def test_approve_user_not_unapproved(
        self,
        pg_user_factory: Callable[..., User],
        pg_company_factory: Callable[..., Company],
        debug: Callable[..., None],
    ) -> None:
        """Verify approving a non-unapproved user raises an error."""
        # Given a player user and an admin
        company = await pg_company_factory()
        admin_user = await pg_user_factory(role=UserRole.ADMIN, company=company)
        player_user = await pg_user_factory(role=UserRole.PLAYER, company=company)

        # When we try to approve a non-unapproved user
        # Then a ValidationError is raised
        service = UserService()
        with pytest.raises(ValidationError, match="not in UNAPPROVED status"):
            await service.approve_user(
                user=player_user,
                role=UserRole.PLAYER,
                requesting_user_id=admin_user.id,
            )

    async def test_approve_user_to_unapproved_role(
        self,
        pg_user_factory: Callable[..., User],
        pg_company_factory: Callable[..., Company],
        debug: Callable[..., None],
    ) -> None:
        """Verify approving a user to the UNAPPROVED role raises an error."""
        # Given an unapproved user and an admin
        company = await pg_company_factory()
        admin_user = await pg_user_factory(role=UserRole.ADMIN, company=company)
        unapproved_user = await pg_user_factory(role=UserRole.UNAPPROVED, company=company)

        # When we try to approve to UNAPPROVED role
        # Then a ValidationError is raised
        service = UserService()
        with pytest.raises(ValidationError, match="Cannot assign UNAPPROVED role"):
            await service.approve_user(
                user=unapproved_user,
                role=UserRole.UNAPPROVED,
                requesting_user_id=admin_user.id,
            )

    async def test_approve_user_non_admin_requesting(
        self,
        pg_user_factory: Callable[..., User],
        pg_company_factory: Callable[..., Company],
        debug: Callable[..., None],
    ) -> None:
        """Verify a non-admin cannot approve users."""
        # Given an unapproved user and a player
        company = await pg_company_factory()
        player_user = await pg_user_factory(role=UserRole.PLAYER, company=company)
        unapproved_user = await pg_user_factory(role=UserRole.UNAPPROVED, company=company)

        # When a non-admin tries to approve
        # Then a PermissionDeniedError is raised
        service = UserService()
        with pytest.raises(PermissionDeniedError, match="not authorized"):
            await service.approve_user(
                user=unapproved_user,
                role=UserRole.PLAYER,
                requesting_user_id=player_user.id,
            )

    async def test_deny_user_success(
        self,
        pg_user_factory: Callable[..., User],
        pg_company_factory: Callable[..., Company],
        debug: Callable[..., None],
    ) -> None:
        """Verify denying an unapproved user archives them."""
        # Given an unapproved user and an admin
        company = await pg_company_factory()
        admin_user = await pg_user_factory(role=UserRole.ADMIN, company=company)
        unapproved_user = await pg_user_factory(role=UserRole.UNAPPROVED, company=company)

        # When we deny the user
        service = UserService()
        await service.deny_user(
            user=unapproved_user,
            company=company,
            requesting_user_id=admin_user.id,
        )

        # Then the user is archived
        unapproved_user = await User.get(id=unapproved_user.id)
        assert unapproved_user.is_archived is True

    async def test_deny_user_not_unapproved(
        self,
        pg_user_factory: Callable[..., User],
        pg_company_factory: Callable[..., Company],
        debug: Callable[..., None],
    ) -> None:
        """Verify denying a non-unapproved user raises an error."""
        # Given a player user and an admin
        company = await pg_company_factory()
        admin_user = await pg_user_factory(role=UserRole.ADMIN, company=company)
        player_user = await pg_user_factory(role=UserRole.PLAYER, company=company)

        # When we try to deny a non-unapproved user
        # Then a ValidationError is raised
        service = UserService()
        with pytest.raises(ValidationError, match="not in UNAPPROVED status"):
            await service.deny_user(
                user=player_user,
                company=company,
                requesting_user_id=admin_user.id,
            )

    async def test_deny_user_non_admin_requesting(
        self,
        pg_user_factory: Callable[..., User],
        pg_company_factory: Callable[..., Company],
        debug: Callable[..., None],
    ) -> None:
        """Verify a non-admin cannot deny users."""
        # Given an unapproved user and a player
        company = await pg_company_factory()
        player_user = await pg_user_factory(role=UserRole.PLAYER, company=company)
        unapproved_user = await pg_user_factory(role=UserRole.UNAPPROVED, company=company)

        # When a non-admin tries to deny
        # Then a PermissionDeniedError is raised
        service = UserService()
        with pytest.raises(PermissionDeniedError, match="not authorized"):
            await service.deny_user(
                user=unapproved_user,
                company=company,
                requesting_user_id=player_user.id,
            )

    async def test_register_user_success(
        self,
        pg_company_factory: Callable[..., Company],
        debug: Callable[..., None],
    ) -> None:
        """Verify register_user creates an UNAPPROVED user without permission checks."""
        # Given a company and registration data
        company = await pg_company_factory()
        data = UserRegister(
            name_first="New",
            name_last="Player",
            username="new_player",
            email="new@example.com",
            google_profile={"email": "new@gmail.com", "username": "New Player"},
        )

        # When we register the user
        service = UserService()
        new_user = await service.register_user(company=company, data=data)

        # Then the user is created with UNAPPROVED role
        assert new_user.name_first == "New"
        assert new_user.name_last == "Player"
        assert new_user.username == "new_player"
        assert new_user.email == "new@example.com"
        assert new_user.role == UserRole.UNAPPROVED
        assert new_user.company_id == company.id
        assert new_user.google_profile["email"] == "new@gmail.com"

    async def test_merge_users_success(
        self,
        pg_company_factory: Callable[..., Company],
        pg_user_factory: Callable[..., User],
        mocker: Any,
        debug: Callable[..., None],
    ) -> None:
        """Verify merge absorbs secondary profile into primary and archives secondary."""
        # Given a company with a primary user and an UNAPPROVED secondary user
        company = await pg_company_factory()
        admin_user = await pg_user_factory(role=UserRole.ADMIN, company=company)
        primary_user = await pg_user_factory(
            company=company,
            discord_profile={"username": "primary_discord"},
            google_profile={},
            github_profile={},
        )
        secondary_user = await pg_user_factory(
            company=company,
            role=UserRole.UNAPPROVED,
            google_profile={"email": "secondary@gmail.com", "username": "Secondary"},
            github_profile={"login": "secondary_gh"},
        )
        spy = mocker.spy(UserService, "remove_and_archive_user")

        # When we merge the users
        service = UserService()
        result = await service.merge_users(
            primary_user_id=primary_user.id,
            secondary_user_id=secondary_user.id,
            company=company,
            requesting_user_id=admin_user.id,
        )

        # Then the primary user has the secondary's profile info
        assert result.google_profile["email"] == "secondary@gmail.com"
        assert result.google_profile["username"] == "Secondary"
        assert result.github_profile["login"] == "secondary_gh"
        assert result.discord_profile["username"] == "primary_discord"

        # Then the secondary user was archived
        spy.assert_called_once()

    async def test_merge_users_secondary_not_unapproved(
        self,
        pg_company_factory: Callable[..., Company],
        pg_user_factory: Callable[..., User],
        debug: Callable[..., None],
    ) -> None:
        """Verify merge rejects if secondary user is not UNAPPROVED."""
        # Given a company with two active users
        company = await pg_company_factory()
        admin_user = await pg_user_factory(role=UserRole.ADMIN, company=company)
        primary_user = await pg_user_factory(company=company)
        secondary_user = await pg_user_factory(company=company, role=UserRole.PLAYER)

        # When we attempt to merge
        # Then a ValidationError is raised
        service = UserService()
        with pytest.raises(ValidationError, match="UNAPPROVED"):
            await service.merge_users(
                primary_user_id=primary_user.id,
                secondary_user_id=secondary_user.id,
                company=company,
                requesting_user_id=admin_user.id,
            )

    async def test_merge_users_same_user(
        self,
        pg_company_factory: Callable[..., Company],
        pg_user_factory: Callable[..., User],
        debug: Callable[..., None],
    ) -> None:
        """Verify merge rejects when primary and secondary are the same user."""
        # Given a company with a user
        company = await pg_company_factory()
        admin_user = await pg_user_factory(role=UserRole.ADMIN, company=company)
        user = await pg_user_factory(company=company, role=UserRole.UNAPPROVED)

        # When we attempt to merge a user with themselves
        # Then a ValidationError is raised
        service = UserService()
        with pytest.raises(ValidationError, match="Cannot merge a user with themselves"):
            await service.merge_users(
                primary_user_id=user.id,
                secondary_user_id=user.id,
                company=company,
                requesting_user_id=admin_user.id,
            )

    async def test_merge_users_non_admin_rejected(
        self,
        pg_company_factory: Callable[..., Company],
        pg_user_factory: Callable[..., User],
        debug: Callable[..., None],
    ) -> None:
        """Verify merge rejects if requesting user is not an admin."""
        # Given a company with users
        company = await pg_company_factory()
        player_user = await pg_user_factory(role=UserRole.PLAYER, company=company)
        primary_user = await pg_user_factory(company=company)
        secondary_user = await pg_user_factory(company=company, role=UserRole.UNAPPROVED)

        # When a non-admin attempts to merge
        # Then a PermissionDeniedError is raised
        service = UserService()
        with pytest.raises(PermissionDeniedError):
            await service.merge_users(
                primary_user_id=primary_user.id,
                secondary_user_id=secondary_user.id,
                company=company,
                requesting_user_id=player_user.id,
            )

    async def test_absorb_profiles_does_not_overwrite(
        self,
        pg_user_factory: Callable[..., User],
        pg_company_factory: Callable[..., Company],
        debug: Callable[..., None],
    ) -> None:
        """Verify _absorb_profiles only fills empty fields on primary."""
        # Given a primary user with some profile info and a secondary with different info
        company = await pg_company_factory()
        primary = await pg_user_factory(
            company=company,
            google_profile={"email": "primary@gmail.com", "username": "PrimaryUser"},
        )
        secondary = await pg_user_factory(
            company=company,
            role=UserRole.UNAPPROVED,
            google_profile={
                "email": "secondary@gmail.com",
                "username": "SecondaryUser",
                "locale": "en",
            },
        )

        # When we absorb profiles
        UserService._absorb_profiles(primary=primary, secondary=secondary)

        # Then primary keeps its existing values and fills in empty ones
        assert primary.google_profile["email"] == "primary@gmail.com"
        assert primary.google_profile["username"] == "PrimaryUser"
        assert primary.google_profile["locale"] == "en"


class TestUserQuickRollService:
    """Test the quick roll service."""

    async def test_validate_quickroll_success(
        self,
        user_factory: Callable[..., BeanieUser],
        debug: Callable[..., None],
    ) -> None:
        """Test the validate_quickroll method."""
        # Given objects
        user = await user_factory()
        trait1 = await Trait.find_one(Trait.is_archived == False)
        trait2 = await Trait.find_one(Trait.is_archived == False, Trait.id != trait1.id)
        quickroll = QuickRoll(
            name="Quick Roll 1", user_id=user.id, trait_ids=[trait1.id, trait2.id]
        )

        # When we validate the quick roll
        service = UserQuickRollService()
        validated_quickroll = await service.validate_quickroll(quickroll)

        # Then the quick roll is validated and returned
        assert validated_quickroll.id == quickroll.id
        assert validated_quickroll.name == quickroll.name
        assert validated_quickroll.user_id == quickroll.user_id
        assert validated_quickroll.trait_ids == [trait1.id, trait2.id]

    async def test_validate_quickroll_name_already_exists(
        self,
        user_factory: Callable[..., BeanieUser],
        debug: Callable[..., None],
        quickroll_factory: Callable[[dict[str, Any]], QuickRoll],
    ) -> None:
        """Test the validate_quickroll method when the name already exists."""
        # Given objects
        user = await user_factory()
        trait1 = await Trait.find_one(Trait.is_archived == False)
        trait2 = await Trait.find_one(Trait.is_archived == False, Trait.id != trait1.id)
        await quickroll_factory(
            name="Quick Roll 1", user_id=user.id, trait_ids=[trait1.id, trait2.id]
        )
        quickroll2 = await quickroll_factory(
            name="Quick Roll 1", user_id=user.id, trait_ids=[trait1.id, trait2.id]
        )

        # When we validate the quick roll
        # Then a ValidationError is raised
        service = UserQuickRollService()
        with pytest.raises(ValidationError, match="Quick roll name already exists"):
            await service.validate_quickroll(quickroll2)

    async def test_validate_quickroll_no_traits(
        self,
        user_factory: Callable[..., BeanieUser],
        debug: Callable[..., None],
    ) -> None:
        """Verify quickroll with no traits raises ValidationError."""
        # Given a quickroll with an empty trait list
        user = await user_factory()
        quickroll = QuickRoll(name="Empty Roll", user_id=user.id, trait_ids=[])

        # When we validate the quick roll
        # Then a ValidationError is raised
        service = UserQuickRollService()
        with pytest.raises(ValidationError, match="Quick roll must have at least one trait"):
            await service.validate_quickroll(quickroll)

    async def test_validate_quickroll_invalid_trait_ids(
        self,
        user_factory: Callable[..., BeanieUser],
        debug: Callable[..., None],
        quickroll_factory: Callable[[dict[str, Any]], QuickRoll],
    ) -> None:
        """Test the validate_quickroll method when the trait ids are invalid."""
        # Given objects
        user = await user_factory()
        trait1 = await Trait.find_one(Trait.is_archived == False)
        from beanie import PydanticObjectId

        quickroll = await quickroll_factory(
            name="Quick Roll 1", user_id=user.id, trait_ids=[trait1.id, PydanticObjectId()]
        )

        # When we validate the quick roll
        # Then a ValidationError is raised
        service = UserQuickRollService()
        with pytest.raises(ValidationError, match="Trait not found"):
            await service.validate_quickroll(quickroll)


class TestUserXPService:
    """Test the XP service."""

    @pytest.mark.parametrize(
        ("user_role", "permission_grant_xp", "same_user", "expected_result"),
        [
            (UserRole.ADMIN, PermissionsGrantXP.UNRESTRICTED, False, True),
            (UserRole.ADMIN, PermissionsGrantXP.STORYTELLER, False, True),
            (UserRole.ADMIN, PermissionsGrantXP.PLAYER, False, True),
            (UserRole.STORYTELLER, PermissionsGrantXP.UNRESTRICTED, False, True),
            (UserRole.STORYTELLER, PermissionsGrantXP.STORYTELLER, False, True),
            (UserRole.STORYTELLER, PermissionsGrantXP.PLAYER, False, True),
            (UserRole.PLAYER, PermissionsGrantXP.UNRESTRICTED, False, True),
            (UserRole.PLAYER, PermissionsGrantXP.STORYTELLER, False, False),
            (UserRole.PLAYER, PermissionsGrantXP.PLAYER, False, False),
            (UserRole.PLAYER, PermissionsGrantXP.UNRESTRICTED, True, True),
            (UserRole.PLAYER, PermissionsGrantXP.STORYTELLER, True, False),
            (UserRole.PLAYER, PermissionsGrantXP.PLAYER, True, True),
        ],
    )
    async def test_validate_user_can_grant_xp(
        self,
        pg_user_factory: Callable[..., User],
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        debug: Callable[..., None],
        user_role: UserRole,
        permission_grant_xp: PermissionsGrantXP,
        same_user: bool,
        expected_result: bool,
    ) -> None:
        """Verify XP grant permission validation for various role/setting combos."""
        # Given a company with specific XP permission settings
        company = await pg_company_factory()
        await CompanySettings.create(company=company, permission_grant_xp=permission_grant_xp)
        company = await Company.filter(id=company.id).prefetch_related("settings").first()

        requesting_user = await pg_user_factory(role=user_role, company=company)
        if same_user:
            target_user = requesting_user
        else:
            target_user = await pg_user_factory(company=company)

        # When we validate the user can grant XP
        service = UserXPService()
        if expected_result:
            await service._validate_user_can_grant_xp(
                company=company,
                requesting_user_id=requesting_user.id,
                target_user_id=target_user.id,
            )
        else:
            with pytest.raises(PermissionDeniedError):
                await service._validate_user_can_grant_xp(
                    company=company,
                    requesting_user_id=requesting_user.id,
                    target_user_id=target_user.id,
                )

    async def test_add_xp_to_campaign_experience_success(
        self,
        pg_company_factory: Callable[..., Company],
        pg_user_factory: Callable[..., User],
        pg_campaign_factory: Callable[..., Campaign],
        mocker: Any,
        debug: Callable[..., None],
    ) -> None:
        """Verify adding XP to a campaign experience succeeds."""
        # Given a company, campaign, and user
        company = await pg_company_factory()
        await CompanySettings.create(company=company)
        company = await Company.filter(id=company.id).prefetch_related("settings").first()
        campaign = await pg_campaign_factory(company=company)
        target_user = await pg_user_factory(company=company)
        requesting_user = target_user

        spy = mocker.spy(UserXPService, "_validate_user_can_grant_xp")
        initial_lifetime_xp = target_user.lifetime_xp

        # When we add XP to the campaign experience
        service = UserXPService()
        campaign_experience = await service.add_xp_to_campaign_experience(
            company=company,
            requesting_user_id=requesting_user.id,
            target_user=target_user,
            campaign_id=campaign.id,
            amount=10,
        )

        # Then the campaign experience is returned with correct values
        spy.assert_called_once()
        assert campaign_experience.campaign_id == campaign.id
        assert campaign_experience.xp_current == 10
        assert campaign_experience.xp_total == 10
        assert campaign_experience.cool_points == 0

        # Then the user's lifetime XP is incremented
        user = await User.get(id=target_user.id)
        assert user.lifetime_xp == initial_lifetime_xp + 10

    async def test_add_xp_to_campaign_experience_no_lifetime_update(
        self,
        pg_company_factory: Callable[..., Company],
        pg_user_factory: Callable[..., User],
        pg_campaign_factory: Callable[..., Campaign],
    ) -> None:
        """Verify lifetime_xp is not updated when update_total is False."""
        # Given a company, campaign, and user
        company = await pg_company_factory()
        campaign = await pg_campaign_factory(company=company)
        target_user = await pg_user_factory(company=company)
        initial_lifetime_xp = target_user.lifetime_xp

        # When we add XP without updating the total
        service = UserXPService()
        await service.add_xp(
            user_id=target_user.id, campaign_id=campaign.id, amount=10, update_total=False
        )

        # Then lifetime_xp remains unchanged
        user = await User.get(id=target_user.id)
        assert user.lifetime_xp == initial_lifetime_xp

    async def test_add_xp_to_campaign_experience_requesting_user_not_found(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_user_factory: Callable[..., User],
        debug: Callable[..., None],
    ) -> None:
        """Verify adding XP with a non-existent requesting user raises ValidationError."""
        # Given a company, campaign, and target user
        company = await pg_company_factory()
        await CompanySettings.create(company=company)
        company = await Company.filter(id=company.id).prefetch_related("settings").first()
        campaign = await pg_campaign_factory(company=company)
        target_user = await pg_user_factory(company=company)

        # When we add XP with a non-existent requesting user
        # Then a ValidationError is raised
        service = UserXPService()
        with pytest.raises(ValidationError, match=r"User.*not found"):
            await service.add_xp_to_campaign_experience(
                company=company,
                requesting_user_id=uuid7(),
                target_user=target_user,
                campaign_id=campaign.id,
                amount=10,
            )

    async def test_add_cp_to_campaign_experience_success(
        self,
        pg_user_factory: Callable[..., User],
        pg_campaign_factory: Callable[..., Campaign],
        pg_company_factory: Callable[..., Company],
        debug: Callable[..., None],
        mocker: Any,
    ) -> None:
        """Verify adding cool points to a campaign experience succeeds."""
        # Given a company, campaign, and user
        company = await pg_company_factory()
        await CompanySettings.create(company=company)
        company = await Company.filter(id=company.id).prefetch_related("settings").first()
        campaign = await pg_campaign_factory(company=company)
        target_user = await pg_user_factory(company=company)
        requesting_user = target_user
        spy = mocker.spy(UserXPService, "_validate_user_can_grant_xp")
        initial_lifetime_cp = target_user.lifetime_cool_points

        # When we add CP to the campaign experience
        service = UserXPService()
        campaign_experience = await service.add_cp_to_campaign_experience(
            company=company,
            requesting_user_id=requesting_user.id,
            target_user=target_user,
            campaign_id=campaign.id,
            amount=1,
        )

        # Then the campaign experience is returned with correct values
        spy.assert_called_once()
        assert campaign_experience.campaign_id == campaign.id
        assert campaign_experience.xp_current == 10
        assert campaign_experience.xp_total == 10
        assert campaign_experience.cool_points == 1

        # Then the user's lifetime cool points are incremented
        user = await User.get(id=target_user.id)
        assert user.lifetime_cool_points == initial_lifetime_cp + 1

    async def test_add_cp_to_campaign_experience_requesting_user_not_found(
        self,
        pg_campaign_factory: Callable[..., Campaign],
        pg_company_factory: Callable[..., Company],
        pg_user_factory: Callable[..., User],
        debug: Callable[..., None],
    ) -> None:
        """Verify adding CP with a non-existent requesting user raises ValidationError."""
        # Given a company, campaign, and target user
        company = await pg_company_factory()
        await CompanySettings.create(company=company)
        company = await Company.filter(id=company.id).prefetch_related("settings").first()
        campaign = await pg_campaign_factory(company=company)
        target_user = await pg_user_factory(company=company)

        # When we add CP with a non-existent requesting user
        # Then a ValidationError is raised
        service = UserXPService()
        with pytest.raises(ValidationError, match=r"User.*not found"):
            await service.add_cp_to_campaign_experience(
                company=company,
                requesting_user_id=uuid7(),
                target_user=target_user,
                campaign_id=campaign.id,
                amount=1,
            )

    async def test_remove_xp_from_campaign_experience_success(
        self,
        pg_company_factory: Callable[..., Company],
        pg_user_factory: Callable[..., User],
        pg_campaign_factory: Callable[..., Campaign],
        debug: Callable[..., None],
    ) -> None:
        """Verify removing XP from a campaign experience succeeds."""
        # Given a company, campaign, and user with existing XP
        company = await pg_company_factory()
        await CompanySettings.create(company=company)
        company = await Company.filter(id=company.id).prefetch_related("settings").first()
        target_user = await pg_user_factory(company=company)
        requesting_user = target_user
        campaign = await pg_campaign_factory(company=company)

        await CampaignExperience.create(
            user=target_user, campaign=campaign, xp_current=10, xp_total=10, cool_points=1
        )

        # When we remove XP from the campaign experience
        service = UserXPService()
        campaign_experience = await service.remove_xp_from_campaign_experience(
            company=company,
            requesting_user_id=requesting_user.id,
            target_user=target_user,
            campaign_id=campaign.id,
            amount=5,
        )

        # Then the campaign experience is returned with reduced XP
        assert campaign_experience.campaign_id == campaign.id
        assert campaign_experience.xp_current == 5
        assert campaign_experience.xp_total == 10
        assert campaign_experience.cool_points == 1

    async def test_remove_xp_from_campaign_experience_requesting_user_not_found(
        self,
        pg_company_factory: Callable[..., Company],
        pg_campaign_factory: Callable[..., Campaign],
        pg_user_factory: Callable[..., User],
        debug: Callable[..., None],
    ) -> None:
        """Verify removing XP with a non-existent requesting user raises ValidationError."""
        # Given a company, campaign, and target user
        company = await pg_company_factory()
        await CompanySettings.create(company=company)
        company = await Company.filter(id=company.id).prefetch_related("settings").first()
        target_user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)

        # When we remove XP with a non-existent requesting user
        # Then a ValidationError is raised
        service = UserXPService()
        with pytest.raises(ValidationError, match=r"User.*not found"):
            await service.remove_xp_from_campaign_experience(
                company=company,
                requesting_user_id=uuid7(),
                target_user=target_user,
                campaign_id=campaign.id,
                amount=5,
            )

    async def test_remove_xp_insufficient_xp(
        self,
        pg_company_factory: Callable[..., Company],
        pg_user_factory: Callable[..., User],
        pg_campaign_factory: Callable[..., Campaign],
        debug: Callable[..., None],
    ) -> None:
        """Verify removing more XP than available raises NotEnoughXPError."""
        # Given a company, campaign, and user with limited XP
        company = await pg_company_factory()
        await CompanySettings.create(company=company)
        company = await Company.filter(id=company.id).prefetch_related("settings").first()
        target_user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)

        await CampaignExperience.create(
            user=target_user, campaign=campaign, xp_current=3, xp_total=3
        )

        # When we try to remove more XP than available
        # Then a NotEnoughXPError is raised
        service = UserXPService()
        with pytest.raises(NotEnoughXPError):
            await service.remove_xp_from_campaign_experience(
                company=company,
                requesting_user_id=target_user.id,
                target_user=target_user,
                campaign_id=campaign.id,
                amount=5,
            )
