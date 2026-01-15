"""Unit tests for user services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from beanie import PydanticObjectId

from vapi.constants import PermissionsGrantXP, UserRole
from vapi.db.models import QuickRoll, Trait
from vapi.db.models.user import CampaignExperience
from vapi.domain.services import UserQuickRollService, UserXPService
from vapi.lib.exceptions import PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.models import Campaign, Company, User

pytestmark = pytest.mark.anyio


class TestUserQuickRollService:
    """Test the quick roll service."""

    async def test_validate_quickroll_success(
        self,
        user_factory: Callable[[], User],
        debug: Callable[[Any], None],
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
        self, user_factory: Callable[[], User], debug: Callable[[Any], None]
    ) -> None:
        """Test the validate_quickroll method when the name already exists."""
        # Given objects
        user = await user_factory()
        trait1 = await Trait.find_one(Trait.is_archived == False)
        trait2 = await Trait.find_one(Trait.is_archived == False, Trait.id != trait1.id)
        quickroll1 = QuickRoll(
            name="Quick Roll 1", user_id=user.id, trait_ids=[trait1.id, trait2.id]
        )
        await quickroll1.save()
        quickroll2 = QuickRoll(
            name="Quick Roll 1", user_id=user.id, trait_ids=[trait1.id, trait2.id]
        )

        # When we validate the quick roll
        # Then a ValidationError is raised
        service = UserQuickRollService()
        with pytest.raises(ValidationError, match="Quick roll name already exists"):
            await service.validate_quickroll(quickroll2)

    async def test_validate_quickroll_invalid_trait_ids(
        self, user_factory: Callable[[], User], debug: Callable[[Any], None]
    ) -> None:
        """Test the validate_quickroll method when the trait ids are invalid."""
        # Given objects
        user = await user_factory()
        trait1 = await Trait.find_one(Trait.is_archived == False)
        quickroll = QuickRoll(
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
        user_factory: Callable[[], User],
        company_factory: Callable[[], Company],
        campaign_factory: Callable[[], Campaign],
        debug: Callable[[Any], None],
        user_role: UserRole,
        permission_grant_xp: PermissionsGrantXP,
        same_user: bool,
        expected_result: bool,
    ) -> None:
        """Test the validate_user_can_grant_xp method."""
        # Given objects
        company = await company_factory()
        company.settings.permission_grant_xp = permission_grant_xp
        await company.save()
        requesting_user = await user_factory(role=user_role, company_id=company.id)
        if same_user:
            target_user = requesting_user
        else:
            target_user = await user_factory(company_id=company.id)

        # When we validate the user can grant XP
        service = UserXPService()
        if expected_result:
            result = await service._validate_user_can_grant_xp(
                company=company,
                requesting_user=requesting_user,
                target_user_id=target_user.id,
            )
            assert result is True
        else:
            with pytest.raises(PermissionDeniedError):
                await service._validate_user_can_grant_xp(
                    company=company,
                    requesting_user=requesting_user,
                    target_user_id=target_user.id,
                )

    async def test_add_xp_to_campaign_experience_success(
        self,
        company_factory: Callable[[], Company],
        user_factory: Callable[[], User],
        campaign_factory: Callable[[], Campaign],
        mocker: Any,
        debug: Callable[[Any], None],
    ) -> None:
        """Test the add_xp_to_campaign_experience method."""
        # Given objects
        company = await company_factory()
        campaign = await campaign_factory(company_id=company.id)
        target_user = await user_factory(company_id=company.id)
        requesting_user = target_user

        spy = mocker.spy(UserXPService, "_validate_user_can_grant_xp")

        # When we add XP to the campaign experience
        service = UserXPService()
        campaign_experience = await service.add_xp_to_campaign_experience(
            company=company,
            requesting_user=requesting_user,
            target_user_id=target_user.id,
            campaign_id=campaign.id,
            amount=10,
        )
        # debug(campaign_experience)

        # Then the campaign experience is returned
        spy.assert_called_once()
        assert campaign_experience.campaign_id == campaign.id
        assert campaign_experience.xp_current == 10
        assert campaign_experience.xp_total == 10
        assert campaign_experience.cool_points == 0

    async def test_add_xp_to_campaign_experience_user_not_found(
        self,
        company_factory: Callable[[], Company],
        campaign_factory: Callable[[], Campaign],
        user_factory: Callable[[], User],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the add_xp_to_campaign_experience method when the user is not found."""
        # Given objects
        company = await company_factory()
        campaign = await campaign_factory(company_id=company.id)
        requesting_user = await user_factory(company_id=company.id)

        # When we add XP to the campaign experience
        service = UserXPService()
        with pytest.raises(ValidationError, match=r"User.*not found"):
            await service.add_xp_to_campaign_experience(
                company=company,
                requesting_user=requesting_user,
                target_user_id=PydanticObjectId(),
                campaign_id=campaign.id,
                amount=10,
            )

    async def test_add_xp_to_campaign_experience_campaign_not_found(
        self,
        company_factory: Callable[[], Company],
        campaign_factory: Callable[[], Campaign],
        user_factory: Callable[[], User],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the add_xp_to_campaign_experience method when the campaign is not found."""
        # Given objects
        company = await company_factory()
        target_user = await user_factory(company_id=company.id)
        requesting_user = target_user

        # When we add XP to the campaign experience
        service = UserXPService()
        with pytest.raises(ValidationError, match=r"Campaign.*not found"):
            await service.add_xp_to_campaign_experience(
                company=company,
                requesting_user=requesting_user,
                target_user_id=target_user.id,
                campaign_id=PydanticObjectId(),
                amount=10,
            )

    async def add_cp_to_campaign_experience_success(
        self,
        user_factory: Callable[[], User],
        campaign_factory: Callable[[], Campaign],
        company_factory: Callable[[], Company],
        debug: Callable[[Any], None],
        mocker: Any,
    ) -> None:
        """Test the add_cp_to_campaign_experience method."""
        # Given objects
        company = await company_factory()
        campaign = await campaign_factory(company_id=company.id)
        target_user = await user_factory(company_id=company.id)
        requesting_user = target_user
        spy = mocker.spy(UserXPService, "_validate_user_can_grant_xp")

        # When we add CP to the campaign experience
        service = UserXPService()
        campaign_experience = await service.add_cp_to_campaign_experience(
            company=company,
            requesting_user=requesting_user,
            target_user_id=target_user.id,
            campaign_id=campaign.id,
            amount=1,
        )
        debug(campaign_experience)

        # Then the campaign experience is returned
        spy.assert_called_once()
        assert campaign_experience.campaign_id == campaign.id
        assert campaign_experience.xp_current == 10
        assert campaign_experience.xp_total == 10
        assert campaign_experience.cool_points == 1

    async def test_add_cp_to_campaign_experience_user_not_found(
        self,
        campaign_factory: Callable[[], Campaign],
        company_factory: Callable[[], Company],
        user_factory: Callable[[], User],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the add_cp_to_campaign_experience method when the user is not found."""
        # Given objects
        company = await company_factory()
        campaign = await campaign_factory(company_id=company.id)
        requesting_user = await user_factory(company_id=company.id)

        service = UserXPService()

        with pytest.raises(ValidationError, match=r"User.*not found"):
            await service.add_cp_to_campaign_experience(
                company=company,
                requesting_user=requesting_user,
                target_user_id=PydanticObjectId(),
                campaign_id=campaign.id,
                amount=1,
            )

    async def test_add_cp_to_campaign_experience_campaign_not_found(
        self,
        company_factory: Callable[[], Company],
        user_factory: Callable[[], User],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the add_cp_to_campaign_experience method when the campaign is not found."""
        # Given objects
        company = await company_factory()
        requesting_user = await user_factory(company_id=company.id)
        target_user = requesting_user
        service = UserXPService()

        with pytest.raises(ValidationError, match=r"Campaign.*not found"):
            await service.add_cp_to_campaign_experience(
                company=company,
                requesting_user=requesting_user,
                target_user_id=target_user.id,
                campaign_id=PydanticObjectId(),
                amount=1,
            )

    async def test_remove_xp_from_campaign_experience_success(
        self,
        company_factory: Callable[[], Company],
        user_factory: Callable[[], User],
        campaign_factory: Callable[[], Campaign],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the remove_xp_from_campaign_experience method."""
        # Given objects
        company = await company_factory()
        target_user = await user_factory(company_id=company.id)
        requesting_user = target_user
        campaign = await campaign_factory(company_id=company.id)

        campaign_experience = CampaignExperience(
            campaign_id=campaign.id,
            xp_current=10,
            xp_total=10,
            cool_points=1,
        )
        target_user.campaign_experience.append(campaign_experience)
        await target_user.save()

        # When we remove XP from the campaign experience
        service = UserXPService()
        campaign_experience = await service.remove_xp_from_campaign_experience(
            company=company,
            requesting_user=requesting_user,
            target_user_id=target_user.id,
            campaign_id=campaign.id,
            amount=5,
        )
        # debug(campaign_experience)

        # Then the campaign experience is returned
        assert campaign_experience.campaign_id == campaign.id
        assert campaign_experience.xp_current == 5
        assert campaign_experience.xp_total == 10
        assert campaign_experience.cool_points == 1

    async def test_remove_xp_from_campaign_experience_user_not_found(
        self,
        company_factory: Callable[[], Company],
        campaign_factory: Callable[[], Campaign],
        user_factory: Callable[[], User],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the remove_xp_from_campaign_experience method when the user is not found."""
        # Given objects
        company = await company_factory()
        requesting_user = await user_factory(company_id=company.id)
        campaign = await campaign_factory(company_id=company.id)
        service = UserXPService()
        with pytest.raises(ValidationError, match=r"User.*not found"):
            await service.remove_xp_from_campaign_experience(
                company=company,
                requesting_user=requesting_user,
                target_user_id=PydanticObjectId(),
                campaign_id=campaign.id,
                amount=5,
            )

    async def test_remove_xp_from_campaign_experience_campaign_not_found(
        self,
        company_factory: Callable[[], Company],
        user_factory: Callable[[], User],
        debug: Callable[[Any], None],
    ) -> None:
        """Test the remove_xp_from_campaign_experience method when the campaign is not found."""
        # Given objects
        company = await company_factory()
        requesting_user = await user_factory(company_id=company.id)
        target_user = requesting_user
        service = UserXPService()
        with pytest.raises(ValidationError, match=r"Campaign.*not found"):
            await service.remove_xp_from_campaign_experience(
                company=company,
                requesting_user=requesting_user,
                target_user_id=target_user.id,
                campaign_id=PydanticObjectId(),
                amount=5,
            )
