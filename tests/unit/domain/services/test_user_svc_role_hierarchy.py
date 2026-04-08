"""Tests for UserService._validate_role_assignment matrix."""

import pytest

from vapi.constants import UserRole
from vapi.domain.services import UserService
from vapi.lib.exceptions import PermissionDeniedError, ValidationError

pytestmark = pytest.mark.anyio

# (requester_role, target_current_role, new_role, should_allow)
MATRIX: list[tuple[UserRole, UserRole, UserRole, bool]] = [
    # ADMIN requester
    (UserRole.ADMIN, UserRole.PLAYER, UserRole.ADMIN, True),
    (UserRole.ADMIN, UserRole.PLAYER, UserRole.STORYTELLER, True),
    (UserRole.ADMIN, UserRole.PLAYER, UserRole.PLAYER, True),
    (UserRole.ADMIN, UserRole.PLAYER, UserRole.DEACTIVATED, True),
    (UserRole.ADMIN, UserRole.PLAYER, UserRole.UNAPPROVED, False),
    (UserRole.ADMIN, UserRole.ADMIN, UserRole.PLAYER, True),
    (UserRole.ADMIN, UserRole.DEACTIVATED, UserRole.PLAYER, True),
    # STORYTELLER requester
    (UserRole.STORYTELLER, UserRole.PLAYER, UserRole.ADMIN, False),
    (UserRole.STORYTELLER, UserRole.PLAYER, UserRole.STORYTELLER, True),
    (UserRole.STORYTELLER, UserRole.PLAYER, UserRole.PLAYER, True),
    (UserRole.STORYTELLER, UserRole.PLAYER, UserRole.DEACTIVATED, False),
    (UserRole.STORYTELLER, UserRole.ADMIN, UserRole.STORYTELLER, False),
    (UserRole.STORYTELLER, UserRole.DEACTIVATED, UserRole.PLAYER, False),
    # Non-privileged requesters
    (UserRole.PLAYER, UserRole.PLAYER, UserRole.PLAYER, False),
    (UserRole.PLAYER, UserRole.PLAYER, UserRole.ADMIN, False),
    (UserRole.UNAPPROVED, UserRole.PLAYER, UserRole.PLAYER, False),
    (UserRole.DEACTIVATED, UserRole.PLAYER, UserRole.PLAYER, False),
]


@pytest.mark.parametrize(("requester_role", "target_role", "new_role", "allow"), MATRIX)
async def test_role_assignment_matrix(
    user_factory, company_factory, requester_role, target_role, new_role, allow
):
    """Verify the role-assignment authorization matrix is enforced."""
    # Given a requester and target with the parametrized roles
    company = await company_factory()
    requester = await user_factory(role=requester_role, company=company)
    target = await user_factory(role=target_role, company=company)

    # When validating the role assignment
    service = UserService()
    if allow:
        # Then no exception is raised
        await service._validate_role_assignment(
            requesting_user=requester, target_user=target, new_role=new_role
        )
    else:
        # Then a permission or validation error is raised
        with pytest.raises((PermissionDeniedError, ValidationError)):
            await service._validate_role_assignment(
                requesting_user=requester, target_user=target, new_role=new_role
            )


async def test_player_cannot_self_escalate_to_admin(user_factory, company_factory):
    """Regression: PATCH /users/{id} by a PLAYER setting own role=ADMIN must fail."""
    from vapi.domain.controllers.user.dto import UserPatch

    company = await company_factory()
    player = await user_factory(role=UserRole.PLAYER, company=company)
    patch = UserPatch(requesting_user_id=player.id, role="ADMIN")
    with pytest.raises(PermissionDeniedError):
        await UserService().update_user(user=player, data=patch)


async def test_player_can_self_update_non_role_field(user_factory, company_factory):
    """Verify non-role self-edits still work after role matrix is wired in."""
    from vapi.domain.controllers.user.dto import UserPatch

    company = await company_factory()
    player = await user_factory(role=UserRole.PLAYER, company=company, name_first="Alice")
    patch = UserPatch(requesting_user_id=player.id, name_first="Bob")
    updated = await UserService().update_user(user=player, data=patch)
    assert updated.name_first == "Bob"
    assert updated.role == UserRole.PLAYER
