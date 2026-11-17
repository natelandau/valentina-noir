"""Tests that user writes from a stale instance keep a concurrent archive or role change."""

from __future__ import annotations

import io
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import pytest
from PIL import Image

from tests.fixtures import build_verified_identity
from vapi.constants import IdentityProvider, UserRole
from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.user import User
from vapi.domain.controllers.global_admin.dto import AdminUserPatch
from vapi.domain.controllers.user.dto import UserPatch
from vapi.domain.services import (
    AvatarService,
    GlobalAdminUserService,
    IdentityService,
    UserService,
    user_svc,
)
from vapi.lib.exceptions import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable
    from uuid import UUID

    from vapi.db.sql_models.company import Company

pytestmark = pytest.mark.anyio


async def _archive_concurrently(user_id: UUID) -> None:
    """Archive a user through a separate instance, as a concurrent request would."""
    await GlobalAdminUserService().delete_user(await User.get(id=user_id))


async def _patch_concurrently(user_id: UUID, **fields: object) -> None:
    """Patch a user through a separate instance, as a concurrent request would."""
    await GlobalAdminUserService().update_user(await User.get(id=user_id), AdminUserPatch(**fields))


def _run_before_transaction(
    monkeypatch: pytest.MonkeyPatch, concurrent_change: Callable[[], Awaitable[None]]
) -> None:
    """Commit a concurrent change once, just before the user service opens its transaction.

    This lands the change after the request loaded its rows and before it locks them.
    """
    original = user_svc.in_transaction
    done = False

    @asynccontextmanager
    async def _change_then_transaction(*args: object, **kwargs: object) -> AsyncIterator[object]:
        nonlocal done
        if not done:
            done = True
            await concurrent_change()
        async with original(*args, **kwargs) as connection:
            yield connection

    monkeypatch.setattr(user_svc, "in_transaction", _change_then_transaction)


async def _tenant_delete(user_id: UUID, company: Company) -> None:
    """Delete a user through the company user service, as a concurrent admin request would."""
    await UserService().remove_and_archive_user(user=await User.get(id=user_id), company=company)


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


def _png_bytes() -> bytes:
    """Build a small PNG for avatar uploads."""
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=(10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


async def test_set_avatar_refused_after_concurrent_archive(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify an avatar upload from a stale instance is refused and cannot un-archive the user."""
    # Given a user loaded before another request archives them (boto3 is mocked autouse)
    company = await company_factory()
    target = await user_factory(company=company)
    stale = await User.get(id=target.id)
    await _archive_concurrently(target.id)

    # When an avatar is set on the stale instance
    # Then the upload is refused, the archive holds, and the uploaded asset is archived
    with pytest.raises(NotFoundError):
        await AvatarService().set_avatar(
            user=stale, company_id=company.id, acting_user_id=target.id, data=_png_bytes()
        )
    stored = await User.get(id=target.id)
    assert stored.is_archived is True
    assert stored.archive_batch_id is not None
    assert stored.avatar_asset_id is None
    orphans = await S3Asset.filter(user_parent_id=target.id, is_archived=False).count()
    assert orphans == 0


async def test_set_avatar_keeps_concurrent_role_change(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify an avatar upload from a stale instance does not write back a removed role."""
    # Given an admin loaded before another admin deactivates them
    company = await company_factory()
    await user_factory(role=UserRole.ADMIN, company=company)
    target = await user_factory(role=UserRole.ADMIN, company=company)
    stale = await User.get(id=target.id)
    await _patch_concurrently(target.id, role=UserRole.DEACTIVATED)

    # When an avatar is set on the stale instance
    updated = await AvatarService().set_avatar(
        user=stale, company_id=company.id, acting_user_id=target.id, data=_png_bytes()
    )

    # Then the avatar is stored and the deactivation holds
    stored = await User.get(id=target.id)
    assert stored.avatar_asset_id == updated.avatar_asset_id is not None
    assert stored.role == UserRole.DEACTIVATED


async def test_remove_avatar_refused_after_concurrent_archive(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify removing an avatar from a stale instance is refused for an archived user."""
    # Given a user with an avatar, loaded before another request archives them
    company = await company_factory()
    target = await user_factory(company=company)
    await AvatarService().set_avatar(
        user=target, company_id=company.id, acting_user_id=target.id, data=_png_bytes()
    )
    stale = await User.get(id=target.id)
    await _archive_concurrently(target.id)

    # When the avatar is removed on the stale instance
    # Then the removal is refused and the archive holds
    with pytest.raises(NotFoundError):
        await AvatarService().remove_avatar(user=stale)
    stored = await User.get(id=target.id)
    assert stored.is_archived is True
    assert stored.archive_batch_id is not None


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


async def test_link_identity_refused_after_concurrent_archive(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify linking on a stale instance cannot write to, or un-archive, an archived user."""
    # Given a user loaded before another request archives them
    company = await company_factory()
    target = await user_factory(company=company)
    stale = await User.get(id=target.id)
    await _archive_concurrently(target.id)

    # When an identity is linked on the stale instance
    # Then the link is refused and the archive holds
    with pytest.raises(NotFoundError):
        await IdentityService().link_identity(
            company=company, user=stale, identity=build_verified_identity()
        )
    stored = await User.get(id=target.id)
    assert stored.is_archived is True
    assert stored.archive_batch_id is not None
    assert stored.apple_profile is None


async def test_link_identity_does_not_trust_concurrently_changed_email(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify an identity proving the old email cannot mark a concurrently changed email trusted."""
    # Given a user loaded before their email changes to one no provider proved
    company = await company_factory()
    target = await user_factory(company=company, email="person@example.com", email_trusted=False)
    stale = await User.get(id=target.id)
    await User.filter(id=target.id).update(email="changed@example.com", email_trusted=False)

    # When an identity verifying the old email is linked on the stale instance
    await IdentityService().link_identity(
        company=company, user=stale, identity=build_verified_identity()
    )

    # Then the new email stays untrusted
    stored = await User.get(id=target.id)
    assert stored.email == "changed@example.com"
    assert stored.email_trusted is False


async def test_unlink_identity_refused_after_concurrent_archive(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify unlinking on a stale instance cannot write to an archived user."""
    # Given a user with two identities, loaded before another request archives them
    company = await company_factory()
    target = await user_factory(
        company=company, apple_profile={"id": "apple-sub-001"}, github_profile={"id": "4242"}
    )
    stale = await User.get(id=target.id)
    await _archive_concurrently(target.id)

    # When the apple identity is unlinked on the stale instance
    # Then the unlink is refused and the archive holds
    with pytest.raises(NotFoundError):
        await IdentityService().unlink_identity(user=stale, provider=IdentityProvider.APPLE)
    stored = await User.get(id=target.id)
    assert stored.is_archived is True
    assert stored.apple_profile == {"id": "apple-sub-001"}


async def test_unlink_identity_counts_identities_on_committed_row(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify a stale unlink cannot remove the last identity left after a concurrent unlink."""
    # Given a user with two identities, loaded before a concurrent request unlinks one
    company = await company_factory()
    target = await user_factory(
        company=company, apple_profile={"id": "apple-sub-001"}, github_profile={"id": "4242"}
    )
    stale = await User.get(id=target.id)
    await IdentityService().unlink_identity(
        user=await User.get(id=target.id), provider=IdentityProvider.GITHUB
    )

    # When the other identity is unlinked on the stale instance
    # Then it is refused as the last identity and stays linked
    with pytest.raises(ConflictError) as exc_info:
        await IdentityService().unlink_identity(user=stale, provider=IdentityProvider.APPLE)
    assert exc_info.value.extension == {"code": "LAST_IDENTITY"}
    stored = await User.get(id=target.id)
    assert stored.apple_profile == {"id": "apple-sub-001"}
    assert stored.github_profile is None


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


async def test_unlink_identity_reports_committed_profile(
    company_factory: Callable[..., Company], user_factory: Callable[..., User]
) -> None:
    """Verify unlink reports the profile it removed, not the one a stale instance loaded."""
    # Given a user loaded before a concurrent request refreshes their apple profile
    company = await company_factory()
    target = await user_factory(
        company=company,
        apple_profile={"id": "apple-sub-001", "email": "old@example.com"},
        github_profile={"id": "4242"},
    )
    stale = await User.get(id=target.id)
    await IdentityService().link_identity(
        company=company, user=await User.get(id=target.id), identity=build_verified_identity()
    )

    # When the apple identity is unlinked on the stale instance
    old_profile = await IdentityService().unlink_identity(
        user=stale, provider=IdentityProvider.APPLE
    )

    # Then the reported profile is the committed one
    assert old_profile == {"id": "apple-sub-001", "email": "person@example.com"}


@pytest.mark.parametrize("revoked_role", [UserRole.PLAYER, UserRole.DEACTIVATED])
async def test_update_user_self_role_refused_after_concurrent_revocation(
    company_factory: Callable[..., Company],
    user_factory: Callable[..., User],
    monkeypatch: pytest.MonkeyPatch,
    revoked_role: UserRole,
) -> None:
    """Verify a self edit in flight cannot restore admin authority revoked concurrently."""
    # Given an admin whose demotion or deactivation commits while their self edit is in flight
    company = await company_factory()
    await user_factory(role=UserRole.ADMIN, company=company)
    target = await user_factory(role=UserRole.ADMIN, company=company)
    stale = await User.get(id=target.id)
    _run_before_transaction(monkeypatch, lambda: _patch_concurrently(target.id, role=revoked_role))

    # When the self edit resends the admin role
    # Then it is refused and the revocation holds
    with pytest.raises(PermissionDeniedError):
        await UserService().update_user(
            stale, UserPatch(name_first="Renamed", role=UserRole.ADMIN), acting_user_id=target.id
        )
    stored = await User.get(id=target.id)
    assert stored.role == revoked_role
    assert stored.name_first == target.name_first


async def test_update_user_refused_after_concurrent_requester_demotion(
    company_factory: Callable[..., Company],
    user_factory: Callable[..., User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify an admin demoted mid-request cannot still change another user's role."""
    # Given an admin demoted while their edit of another user is in flight
    company = await company_factory()
    await user_factory(role=UserRole.ADMIN, company=company)
    admin = await user_factory(role=UserRole.ADMIN, company=company)
    target = await user_factory(role=UserRole.PLAYER, company=company)
    stale = await User.get(id=target.id)
    _run_before_transaction(
        monkeypatch, lambda: _patch_concurrently(admin.id, role=UserRole.PLAYER)
    )

    # When the demoted admin's request promotes the target
    # Then it is refused and the target keeps their role
    with pytest.raises(PermissionDeniedError):
        await UserService().update_user(
            stale, UserPatch(role=UserRole.ADMIN), acting_user_id=admin.id
        )
    stored = await User.get(id=target.id)
    assert stored.role == UserRole.PLAYER


async def test_update_user_self_edit_refused_after_concurrent_delete(
    company_factory: Callable[..., Company],
    user_factory: Callable[..., User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a self edit in flight cannot un-delete the user or detach their archive batch."""
    # Given a user deleted while their self edit is in flight
    company = await company_factory()
    await user_factory(role=UserRole.ADMIN, company=company)
    target = await user_factory(role=UserRole.PLAYER, company=company)
    stale = await User.get(id=target.id)
    _run_before_transaction(monkeypatch, lambda: _tenant_delete(target.id, company))

    # When the self edit saves a name change
    # Then it is refused and the archive and its batch id hold
    with pytest.raises(NotFoundError):
        await UserService().update_user(
            stale, UserPatch(name_first="Renamed"), acting_user_id=target.id
        )
    stored = await User.get(id=target.id)
    assert stored.is_archived is True
    assert stored.archive_batch_id is not None
    assert stored.name_first == target.name_first


async def test_merge_users_refused_after_concurrent_primary_delete(
    company_factory: Callable[..., Company],
    user_factory: Callable[..., User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify a merge cannot absorb into, or archive the secondary for, a primary deleted mid-request."""
    # Given a primary user deleted while the merge is in flight
    company = await company_factory()
    admin = await user_factory(role=UserRole.ADMIN, company=company)
    primary = await user_factory(role=UserRole.PLAYER, company=company)
    secondary = await user_factory(role=UserRole.UNAPPROVED, company=company)
    _run_before_transaction(monkeypatch, lambda: _tenant_delete(primary.id, company))

    # When the admin merges the secondary into the deleted primary
    # Then the merge is refused and the secondary stays active
    with pytest.raises(NotFoundError):
        await UserService().merge_users(
            primary_user_id=primary.id,
            secondary_user_id=secondary.id,
            company=company,
            acting_user_id=admin.id,
        )
    stored_secondary = await User.get(id=secondary.id)
    assert stored_secondary.is_archived is False
