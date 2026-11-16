"""Tests that user writes from a stale instance keep a concurrent archive or role change."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
from PIL import Image

from tests.fixtures import build_verified_identity
from vapi.constants import UserRole
from vapi.db.sql_models.user import User
from vapi.domain.controllers.global_admin.dto import AdminUserPatch
from vapi.domain.controllers.user.dto import UserPatch
from vapi.domain.services import (
    AvatarService,
    GlobalAdminUserService,
    IdentityService,
    UserService,
)
from vapi.lib.exceptions import NotFoundError, ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable
    from uuid import UUID

    from vapi.db.sql_models.company import Company

pytestmark = pytest.mark.anyio


async def _archive_concurrently(user_id: UUID) -> None:
    """Archive a user through a separate instance, as a concurrent request would."""
    await GlobalAdminUserService().delete_user(await User.get(id=user_id))


async def _patch_concurrently(user_id: UUID, **fields: object) -> None:
    """Patch a user through a separate instance, as a concurrent request would."""
    await GlobalAdminUserService().update_user(await User.get(id=user_id), AdminUserPatch(**fields))


async def test_update_user_refused_after_concurrent_archive(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify an admin's edit of a stale user cannot un-archive them."""
    # Given a user loaded before another request archives them
    company = await company_factory()
    admin = await user_factory(role=UserRole.ADMIN, company=company)
    target = await user_factory(role=UserRole.PLAYER, company=company)
    stale = await User.get(id=target.id)
    await _archive_concurrently(target.id)

    # When the admin saves a name change from the stale instance
    # Then the edit is refused and the archive holds
    with pytest.raises(NotFoundError):
        await UserService().update_user(
            stale, UserPatch(name_first="Renamed"), acting_user_id=admin.id
        )
    stored = await User.get(id=target.id)
    assert stored.is_archived is True
    assert stored.name_first == target.name_first


async def test_update_user_keeps_concurrent_role_change(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify a self edit from a stale instance cannot restore a role removed concurrently."""
    # Given a storyteller loaded before an admin deactivates them
    company = await company_factory()
    await user_factory(role=UserRole.ADMIN, company=company)
    target = await user_factory(role=UserRole.STORYTELLER, company=company)
    stale = await User.get(id=target.id)
    await _patch_concurrently(target.id, role=UserRole.PLAYER)

    # When the user saves a name change to themselves from the stale instance
    await UserService().update_user(
        stale, UserPatch(name_first="Renamed"), acting_user_id=target.id
    )

    # Then the name changes and the role change holds
    stored = await User.get(id=target.id)
    assert stored.name_first == "Renamed"
    assert stored.role == UserRole.PLAYER


async def test_approve_user_refused_after_concurrent_deny(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify approving a stale unapproved user cannot resurrect a user denied concurrently."""
    # Given an unapproved user loaded before another admin denies them
    company = await company_factory()
    admin = await user_factory(role=UserRole.ADMIN, company=company)
    target = await user_factory(role=UserRole.UNAPPROVED, company=company)
    stale = await User.get(id=target.id)
    await UserService().deny_user(
        user=await User.get(id=target.id), company=company, acting_user_id=admin.id
    )

    # When the admin approves the stale instance
    # Then the approval is refused and the user stays archived and unapproved
    with pytest.raises(ValidationError):
        await UserService().approve_user(user=stale, role=UserRole.PLAYER, acting_user_id=admin.id)
    stored = await User.get(id=target.id)
    assert stored.is_archived is True
    assert stored.role == UserRole.UNAPPROVED


async def test_remove_and_archive_user_keeps_concurrent_role_change(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify archiving a stale user does not write back their old role."""
    # Given a storyteller loaded before their role is lowered
    company = await company_factory()
    await user_factory(role=UserRole.ADMIN, company=company)
    target = await user_factory(role=UserRole.STORYTELLER, company=company)
    stale = await User.get(id=target.id)
    await _patch_concurrently(target.id, role=UserRole.PLAYER)

    # When the stale instance is archived
    await UserService().remove_and_archive_user(user=stale, company=company)

    # Then the user is archived and keeps the lowered role
    stored = await User.get(id=target.id)
    assert stored.is_archived is True
    assert stored.role == UserRole.PLAYER


async def test_global_admin_update_keeps_concurrent_archive(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify a global admin's name edit from a stale instance does not un-archive the user."""
    # Given a user loaded before another request archives them
    company = await company_factory()
    target = await user_factory(company=company)
    stale = await User.get(id=target.id)
    await _archive_concurrently(target.id)

    # When the global admin saves a name change from the stale instance
    await GlobalAdminUserService().update_user(stale, AdminUserPatch(name_first="Renamed"))

    # Then the name changes and the archive holds
    stored = await User.get(id=target.id)
    assert stored.name_first == "Renamed"
    assert stored.is_archived is True


async def test_global_admin_delete_keeps_concurrent_role_change(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify a global admin delete from a stale instance does not write back the old role."""
    # Given an admin loaded before their role is lowered
    company = await company_factory()
    target = await user_factory(role=UserRole.ADMIN, company=company)
    stale = await User.get(id=target.id)
    await _patch_concurrently(target.id, role=UserRole.PLAYER)

    # When the stale instance is deleted
    await GlobalAdminUserService().delete_user(stale)

    # Then the user is archived and keeps the lowered role
    stored = await User.get(id=target.id)
    assert stored.is_archived is True
    assert stored.role == UserRole.PLAYER


async def test_set_avatar_keeps_concurrent_archive(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify an avatar upload from a stale instance does not un-archive the user."""
    # Given a user loaded before another request archives them (boto3 is mocked autouse)
    company = await company_factory()
    target = await user_factory(company=company)
    stale = await User.get(id=target.id)
    await _archive_concurrently(target.id)
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(10, 20, 30)).save(buf, format="PNG")

    # When an avatar is set on the stale instance
    await AvatarService().set_avatar(
        user=stale, company_id=company.id, acting_user_id=target.id, data=buf.getvalue()
    )

    # Then the archive holds
    stored = await User.get(id=target.id)
    assert stored.is_archived is True


async def test_link_identity_keeps_concurrent_role_change(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify linking an identity on a stale instance does not write back the old role."""
    # Given an admin loaded before their role is lowered
    company = await company_factory()
    target = await user_factory(role=UserRole.ADMIN, company=company)
    stale = await User.get(id=target.id)
    await _patch_concurrently(target.id, role=UserRole.PLAYER)

    # When an identity is linked on the stale instance
    await IdentityService().link_identity(
        company=company, user=stale, identity=build_verified_identity()
    )

    # Then the identity is stored and the role change holds
    stored = await User.get(id=target.id)
    assert stored.apple_profile is not None
    assert stored.role == UserRole.PLAYER


async def test_update_user_diffs_against_locked_row(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify a patch resending the loaded value still overwrites a concurrent change."""
    # Given a user loaded before another request renames them
    company = await company_factory()
    admin = await user_factory(role=UserRole.ADMIN, company=company)
    target = await user_factory(role=UserRole.PLAYER, company=company, name_first="Original")
    stale = await User.get(id=target.id)
    await _patch_concurrently(target.id, name_first="Concurrent")

    # When an admin sets the name the stale instance loaded
    _, changes = await UserService().update_user(
        stale, UserPatch(name_first="Original"), acting_user_id=admin.id
    )

    # Then the patch is applied and audited against the stored value
    stored = await User.get(id=target.id)
    assert stored.name_first == "Original"
    assert changes == {"name_first": {"old": "Concurrent", "new": "Original"}}


async def test_deny_user_refused_after_concurrent_approval(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify denying a stale unapproved user cannot archive a user approved concurrently."""
    # Given an unapproved user loaded before another admin approves them
    company = await company_factory()
    admin = await user_factory(role=UserRole.ADMIN, company=company)
    target = await user_factory(role=UserRole.UNAPPROVED, company=company)
    stale = await User.get(id=target.id)
    await UserService().approve_user(
        user=await User.get(id=target.id), role=UserRole.PLAYER, acting_user_id=admin.id
    )

    # When the admin denies the stale instance
    # Then the denial is refused and the approved user stays active
    with pytest.raises(ValidationError):
        await UserService().deny_user(user=stale, company=company, acting_user_id=admin.id)
    stored = await User.get(id=target.id)
    assert stored.is_archived is False
    assert stored.role == UserRole.PLAYER
