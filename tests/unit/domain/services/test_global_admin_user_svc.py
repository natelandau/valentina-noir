"""Test the global-admin user service."""

from typing import Any
from uuid import uuid4

import pytest

from vapi.constants import UserRole
from vapi.db.sql_models.character import Character, Specialty
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import User
from vapi.domain.controllers.global_admin.dto import AdminUserCreate, AdminUserPatch
from vapi.domain.handlers import archive_company
from vapi.domain.services import GlobalAdminUserService
from vapi.lib.exceptions import ConflictError, NotFoundError, ValidationError

pytestmark = pytest.mark.anyio


async def test_create_user_with_valid_role(company_factory: Any) -> None:
    """Verify the service creates a user with a valid role."""
    # Given a company and a valid create payload
    company = await company_factory()
    data = AdminUserCreate(
        company_id=company.id,
        username="svc-create-user",
        email="svc-create-user@example.com",
        role="PLAYER",
    )

    # When creating the user via the service
    user = await GlobalAdminUserService().create_user(data)

    # Then the user has the requested role and company
    assert user.role == UserRole.PLAYER
    assert user.company_id == company.id  # type: ignore[attr-defined]

    # Cleanup: service-created users are not factory-tracked
    await user.delete()


@pytest.mark.parametrize("bad_role", ["UNAPPROVED", "DEACTIVATED"])
async def test_create_user_rejects_unassignable_roles(company_factory: Any, bad_role: str) -> None:
    """Verify the service rejects UNAPPROVED and DEACTIVATED as initial roles."""
    # Given a company and a create payload with a non-assignable role
    company = await company_factory()
    data = AdminUserCreate(
        company_id=company.id,
        username="svc-bad-role",
        email="svc-bad-role@example.com",
        role=bad_role,
    )

    # When/Then creating the user raises ValidationError
    with pytest.raises(ValidationError):
        await GlobalAdminUserService().create_user(data)


async def test_create_user_rejects_invalid_role(company_factory: Any) -> None:
    """Verify the service rejects a role that is not a UserRole."""
    # Given a company and a create payload with a nonsense role
    company = await company_factory()
    data = AdminUserCreate(
        company_id=company.id,
        username="svc-invalid-role",
        email="svc-invalid-role@example.com",
        role="WIZARD",
    )

    # When/Then creating the user raises ValidationError
    with pytest.raises(ValidationError):
        await GlobalAdminUserService().create_user(data)


async def test_create_user_unknown_company_raises(company_factory: Any) -> None:
    """Verify the service raises when the target company does not exist."""
    # Given a create payload referencing a nonexistent company
    data = AdminUserCreate(
        company_id=uuid4(),
        username="svc-no-company",
        email="svc-no-company@example.com",
        role="PLAYER",
    )

    # When/Then creating the user raises NotFoundError
    with pytest.raises(NotFoundError):
        await GlobalAdminUserService().create_user(data)


async def test_update_user_changes_role_and_returns_diff(
    company_factory: Any, user_factory: Any
) -> None:
    """Verify update changes the role and reports the diff."""
    # Given a PLAYER user
    company = await company_factory()
    user = await user_factory(company=company, role="PLAYER")

    # When updating the role via the service
    updated, changes = await GlobalAdminUserService().update_user(
        user, AdminUserPatch(role="ADMIN")
    )

    # Then the role is the new enum and the diff records the change
    assert updated.role == UserRole.ADMIN
    assert changes["role"]["new"] == UserRole.ADMIN


async def test_update_user_restores_archived(company_factory: Any, user_factory: Any) -> None:
    """Verify setting is_archived=false restores a soft-deleted user."""
    # Given an archived user
    company = await company_factory()
    user = await user_factory(company=company, is_archived=True)

    # When updating is_archived to false via the service
    updated, _ = await GlobalAdminUserService().update_user(user, AdminUserPatch(is_archived=False))

    # Then the user is no longer archived
    assert updated.is_archived is False


async def test_delete_user_soft_deletes(company_factory: Any, user_factory: Any) -> None:
    """Verify delete archives the user."""
    # Given a user
    company = await company_factory()
    user = await user_factory(company=company)

    # When deleting via the service
    await GlobalAdminUserService().delete_user(user)

    # Then the user is archived
    assert user.is_archived is True


async def test_update_user_archiving_cascades_to_owned_data(
    company_factory: Any, user_factory: Any, quickroll_factory: Any
) -> None:
    """Verify archiving a user via patch cascades archival to their owned data."""
    # Given an active user with a quickroll
    company = await company_factory()
    user = await user_factory(company=company)
    quickroll = await quickroll_factory(user=user)

    # When the user is archived via update
    await GlobalAdminUserService().update_user(user, AdminUserPatch(is_archived=True))

    # Then the user's quickroll is archived too (same cascade as delete)
    assert (await QuickRoll.get(id=quickroll.id)).is_archived is True


async def test_update_user_restore_reverses_cascade_on_owned_data(
    company_factory: Any,
    user_factory: Any,
    character_factory: Any,
    specialty_factory: Any,
    quickroll_factory: Any,
) -> None:
    """Verify restoring a user reverses the archival cascade on owned data."""
    # Given an active company, a user, a played character with a specialty, and a quickroll
    company = await company_factory()
    user = await user_factory(company=company)
    character = await character_factory(company=company, user_player=user)
    specialty = await specialty_factory(character=character)
    quickroll = await quickroll_factory(user=user)

    # Given the user (and their owned data) is archived via the delete cascade
    await GlobalAdminUserService().delete_user(user)
    assert (await Character.get(id=character.id)).is_archived is True
    assert (await Specialty.get(id=specialty.id)).is_archived is True
    assert (await QuickRoll.get(id=quickroll.id)).is_archived is True

    # When the user is restored via update
    await GlobalAdminUserService().update_user(user, AdminUserPatch(is_archived=False))

    # Then the user and every cascade-archived row is active again with no batch stamp
    for model, row_id in (
        (User, user.id),
        (Character, character.id),
        (Specialty, specialty.id),
        (QuickRoll, quickroll.id),
    ):
        restored = await model.get(id=row_id)
        assert restored.is_archived is False
        assert restored.archive_batch_id is None


async def test_update_user_restore_refused_while_company_archived(
    company_factory: Any, user_factory: Any
) -> None:
    """Verify restoring a user is refused while their company is archived."""
    # Given a user whose company has been archived as a whole tenant
    company = await company_factory()
    user = await user_factory(company=company)
    await archive_company(company)
    # Re-fetch so the in-memory user reflects the archived state set by the cascade
    user = await User.get(id=user.id)

    # When/Then restoring the user via update raises ConflictError
    with pytest.raises(ConflictError):
        await GlobalAdminUserService().update_user(user, AdminUserPatch(is_archived=False))
