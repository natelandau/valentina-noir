"""Tests for UserService._assert_requester_active."""

import pytest

from vapi.constants import UserRole
from vapi.domain.services import UserService
from vapi.lib.exceptions import PermissionDeniedError

pytestmark = pytest.mark.anyio


async def test_assert_requester_active_rejects_deactivated(user_factory, company_factory):
    """Verify deactivated users are rejected."""
    company = await company_factory()
    requester = await user_factory(role=UserRole.DEACTIVATED, company=company)
    with pytest.raises(PermissionDeniedError, match="deactivated"):
        await UserService()._assert_requester_active(requester.id)


async def test_assert_requester_active_rejects_unapproved(user_factory, company_factory):
    """Verify unapproved users are rejected."""
    company = await company_factory()
    requester = await user_factory(role=UserRole.UNAPPROVED, company=company)
    with pytest.raises(PermissionDeniedError, match="approved"):
        await UserService()._assert_requester_active(requester.id)


async def test_assert_requester_active_allows_player(user_factory, company_factory):
    """Verify active users are allowed."""
    company = await company_factory()
    requester = await user_factory(role=UserRole.PLAYER, company=company)
    await UserService()._assert_requester_active(requester.id)
