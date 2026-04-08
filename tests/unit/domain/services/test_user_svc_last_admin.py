"""Tests for UserService._assert_not_last_admin."""

import pytest

from vapi.constants import UserRole
from vapi.domain.services import UserService
from vapi.lib.exceptions import ConflictError


async def test_assert_not_last_admin_sole_admin_raises(user_factory, company_factory):
    """Verify removing the sole admin raises ConflictError."""
    # Given a company with a single admin
    company = await company_factory()
    sole_admin = await user_factory(role=UserRole.ADMIN, company=company)

    # When / Then the helper rejects the mutation
    with pytest.raises(ConflictError, match="last admin"):
        await UserService()._assert_not_last_admin(sole_admin)


async def test_assert_not_last_admin_one_of_two_allowed(user_factory, company_factory):
    """Verify one of two admins may be demoted without conflict."""
    # Given a company with two admins
    company = await company_factory()
    admin_a = await user_factory(role=UserRole.ADMIN, company=company)
    await user_factory(role=UserRole.ADMIN, company=company)

    # When / Then the helper allows the mutation
    await UserService()._assert_not_last_admin(admin_a)


async def test_assert_not_last_admin_non_admin_target_noop(user_factory, company_factory):
    """Verify a non-admin target bypasses the check entirely."""
    # Given a company with an admin and a player
    company = await company_factory()
    await user_factory(role=UserRole.ADMIN, company=company)
    player = await user_factory(role=UserRole.PLAYER, company=company)

    # When / Then the helper is a no-op for non-admin targets
    await UserService()._assert_not_last_admin(player)
