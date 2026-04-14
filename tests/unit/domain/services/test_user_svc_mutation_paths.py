"""Tests for hierarchy + active-requester enforcement across mutation paths."""

import pytest

from vapi.constants import UserRole
from vapi.domain.controllers.user.dto import UserCreate
from vapi.domain.services import UserService, UserXPService
from vapi.lib.exceptions import (
    ConflictError,
    PermissionDeniedError,
    ValidationError,
)


async def test_create_user_rejects_storyteller_creating_admin(user_factory, company_factory):
    """Verify a storyteller cannot create a user with the ADMIN role."""
    company = await company_factory()
    storyteller = await user_factory(role=UserRole.STORYTELLER, company=company)
    data = UserCreate(
        username="new",
        email="new@example.com",
        role="ADMIN",
    )
    with pytest.raises(PermissionDeniedError):
        await UserService().create_user(company=company, data=data, acting_user_id=storyteller.id)


async def test_create_user_forbids_deactivated_initial_role(user_factory, company_factory):
    """Verify user creation rejects DEACTIVATED as the initial role."""
    company = await company_factory()
    admin = await user_factory(role=UserRole.ADMIN, company=company)
    data = UserCreate(
        username="new",
        email="new@example.com",
        role="DEACTIVATED",
    )
    with pytest.raises(ValidationError):
        await UserService().create_user(company=company, data=data, acting_user_id=admin.id)


async def test_create_user_forbids_unapproved_initial_role(user_factory, company_factory):
    """Verify user creation rejects UNAPPROVED as the initial role."""
    company = await company_factory()
    admin = await user_factory(role=UserRole.ADMIN, company=company)
    data = UserCreate(
        username="new",
        email="new@example.com",
        role="UNAPPROVED",
    )
    with pytest.raises(ValidationError):
        await UserService().create_user(company=company, data=data, acting_user_id=admin.id)


async def test_approve_user_storyteller_cannot_assign_admin(user_factory, company_factory):
    """Verify a storyteller cannot approve a user into the ADMIN role."""
    company = await company_factory()
    storyteller = await user_factory(role=UserRole.STORYTELLER, company=company)
    target = await user_factory(role=UserRole.UNAPPROVED, company=company)
    with pytest.raises(PermissionDeniedError):
        await UserService().approve_user(
            user=target,
            role=UserRole.ADMIN,
            acting_user_id=storyteller.id,
        )


async def test_delete_last_admin_raises_conflict(user_factory, company_factory):
    """Verify archiving the last remaining admin raises a conflict."""
    company = await company_factory()
    sole_admin = await user_factory(role=UserRole.ADMIN, company=company)
    with pytest.raises(ConflictError):
        await UserService().remove_and_archive_user(user=sole_admin, company=company)


async def test_delete_one_of_two_admins_succeeds(user_factory, company_factory):
    """Verify archiving one of two admins succeeds when another admin remains."""
    company = await company_factory()
    admin_a = await user_factory(role=UserRole.ADMIN, company=company)
    await user_factory(role=UserRole.ADMIN, company=company)
    await UserService().remove_and_archive_user(user=admin_a, company=company)
    assert admin_a.is_archived is True


async def test_xp_grant_rejects_deactivated_requester(
    user_factory, company_factory, campaign_factory
):
    """Verify XP grants reject requesters whose account is DEACTIVATED."""
    company = await company_factory()
    requester = await user_factory(role=UserRole.DEACTIVATED, company=company)
    target = await user_factory(role=UserRole.PLAYER, company=company)
    campaign = await campaign_factory(company=company)
    with pytest.raises(PermissionDeniedError):
        await UserXPService().add_xp_to_campaign_experience(
            company=company,
            acting_user_id=requester.id,
            target_user=target,
            campaign_id=campaign.id,
            amount=5,
        )
