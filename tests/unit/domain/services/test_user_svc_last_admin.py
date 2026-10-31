"""Tests for UserService._assert_not_last_admin."""

import asyncio

import pytest

from vapi.constants import UserRole
from vapi.db.sql_models.user import User
from vapi.domain.controllers.user.dto import UserPatch
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


async def test_update_user_sequential_demotions_keep_one_admin(user_factory, company_factory):
    """Verify admins demoting in turn cannot demote the final admin."""
    # Given a company with two admins
    company = await company_factory()
    admin_a = await user_factory(role=UserRole.ADMIN, company=company)
    admin_b = await user_factory(role=UserRole.ADMIN, company=company)
    service = UserService()

    # When admin A demotes admin B, then tries to demote itself
    await service.update_user(
        user=admin_b, data=UserPatch(role=UserRole.PLAYER.value), acting_user_id=admin_a.id
    )
    with pytest.raises(ConflictError, match="last admin"):
        await service.update_user(
            user=admin_a, data=UserPatch(role=UserRole.PLAYER.value), acting_user_id=admin_a.id
        )

    # Then the self-demotion is refused and one admin remains
    assert await User.filter(company=company, role=UserRole.ADMIN, is_archived=False).count() == 1


async def test_concurrent_admin_archives_keep_one_admin(user_factory, company_factory):
    """Verify archiving two admins at once still leaves one admin."""
    # Given two admins and a service whose first last-admin check pauses until released
    company = await company_factory()
    admin_a = await user_factory(role=UserRole.ADMIN, company=company)
    admin_b = await user_factory(role=UserRole.ADMIN, company=company)
    service = UserService()

    first_checked = asyncio.Event()
    release_first = asyncio.Event()
    real_check = service._assert_not_last_admin

    async def paused_check(target_user: User) -> None:
        await real_check(target_user)
        if not first_checked.is_set():
            first_checked.set()
            await release_first.wait()

    service._assert_not_last_admin = paused_check  # type: ignore[method-assign]

    # When both admins are archived while the first archive is mid-check
    first = asyncio.create_task(service.remove_and_archive_user(user=admin_a, company=company))
    await asyncio.wait_for(first_checked.wait(), timeout=5)
    second = asyncio.create_task(service.remove_and_archive_user(user=admin_b, company=company))
    await asyncio.sleep(0.2)
    release_first.set()
    results = await asyncio.wait_for(
        asyncio.gather(first, second, return_exceptions=True), timeout=5
    )

    # Then the first archive wins, the second conflicts, and one admin remains
    assert results[0] is None
    assert isinstance(results[1], ConflictError)
    assert await User.filter(company=company, role=UserRole.ADMIN, is_archived=False).count() == 1
