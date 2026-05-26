"""Tests for UserService._assert_requester_active."""

import pytest

from vapi.constants import UserRole
from vapi.domain.services import UserService
from vapi.lib.exceptions import PermissionDeniedError

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("role", "match_pattern"),
    [
        (UserRole.DEACTIVATED, "deactivated"),
        (UserRole.UNAPPROVED, "approved"),
    ],
    ids=["deactivated", "unapproved"],
)
async def test_assert_requester_active_rejects_inactive_user(
    user_factory, company_factory, role: UserRole, match_pattern: str
):
    """Verify deactivated and unapproved users are rejected."""
    # Given a user with an inactive role
    company = await company_factory()
    requester = await user_factory(role=role, company=company)

    # When asserting the requester is active, Then a PermissionDeniedError is raised
    with pytest.raises(PermissionDeniedError, match=match_pattern):
        await UserService()._assert_requester_active(requester.id)


async def test_assert_requester_active_allows_player(user_factory, company_factory):
    """Verify active users are allowed."""
    company = await company_factory()
    requester = await user_factory(role=UserRole.PLAYER, company=company)
    await UserService()._assert_requester_active(requester.id)
