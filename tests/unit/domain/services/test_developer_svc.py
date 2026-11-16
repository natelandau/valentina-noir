"""Unit tests for DeveloperService."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vapi.db.sql_models.developer import Developer
from vapi.domain.controllers.developer.dto import DeveloperPatch
from vapi.domain.controllers.global_admin.dto import AdminDeveloperPatch
from vapi.domain.services import DeveloperService
from vapi.lib.exceptions import NotAuthorizedError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


class TestGenerateApiKey:
    """Tests for DeveloperService.generate_api_key."""

    async def test_generate_api_key(self, developer_factory: Callable[..., Developer]) -> None:
        """Verify generate_api_key returns a 32-char key and persists hash fields."""
        # Given a developer with no key material
        developer = await developer_factory()

        # When generating an API key
        service = DeveloperService()
        key = await service.generate_api_key(developer)

        # Then the returned key is a 32-character string
        assert isinstance(key, str)
        assert len(key) == 32

        # And the DB record has all key fields populated
        refreshed = await Developer.get(id=str(developer.id))
        assert refreshed.hashed_api_key is not None
        assert refreshed.api_key_fingerprint is not None
        assert refreshed.key_generated is not None


async def _admin_set(developer_id: object, **values: object) -> None:
    """Change a developer through a separate instance, as a concurrent global admin would."""
    admin_copy = await Developer.get(id=developer_id)
    for name, value in values.items():
        setattr(admin_copy, name, value)
    await admin_copy.save()


async def _admin_rotate(developer_id: object) -> Developer:
    """Rotate a developer's key through a separate instance and return that instance."""
    admin_copy = await Developer.get(id=developer_id)
    await DeveloperService().generate_api_key(admin_copy)
    return admin_copy


class TestRevocationDuringSelfEdit:
    """A global-admin revocation made after the developer was loaded must survive the self edit."""

    async def test_self_key_rotation_refused_after_archive(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify a self key rotation on a stale instance cannot un-archive the developer."""
        # Given a developer loaded before a global admin archives it
        service = DeveloperService()
        developer = await developer_factory()
        await service.generate_api_key(developer)
        stale = await Developer.get(id=developer.id)
        await _admin_set(developer.id, is_archived=True)

        # When the developer rotates their own key from the stale instance
        # Then the rotation is refused and the archive holds
        with pytest.raises(NotAuthorizedError):
            await service.generate_api_key(stale, expected_fingerprint=stale.api_key_fingerprint)
        refreshed = await Developer.get(id=developer.id)
        assert refreshed.is_archived is True
        assert refreshed.api_key_fingerprint == developer.api_key_fingerprint

    async def test_self_key_rotation_refused_after_admin_rotation(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify a self key rotation cannot replace a key a global admin issued after load."""
        # Given a developer loaded before a global admin rotates its key
        service = DeveloperService()
        developer = await developer_factory()
        await service.generate_api_key(developer)
        stale = await Developer.get(id=developer.id)
        admin_copy = await _admin_rotate(developer.id)

        # When the developer rotates their own key from the stale instance
        # Then the rotation is refused and the admin-issued key holds
        with pytest.raises(NotAuthorizedError):
            await service.generate_api_key(stale, expected_fingerprint=stale.api_key_fingerprint)
        refreshed = await Developer.get(id=developer.id)
        assert refreshed.api_key_fingerprint == admin_copy.api_key_fingerprint

    async def test_key_rotation_keeps_concurrent_demotion(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify a key rotation on a stale instance does not restore is_global_admin."""
        # Given a global admin developer loaded before it is demoted
        service = DeveloperService()
        developer = await developer_factory(is_global_admin=True)
        await service.generate_api_key(developer)
        stale = await Developer.get(id=developer.id)
        await _admin_set(developer.id, is_global_admin=False)

        # When the developer rotates their own key from the stale instance
        await service.generate_api_key(stale, expected_fingerprint=stale.api_key_fingerprint)

        # Then the demotion holds
        refreshed = await Developer.get(id=developer.id)
        assert refreshed.is_global_admin is False
        assert refreshed.api_key_fingerprint == stale.api_key_fingerprint

    async def test_admin_key_rotation_refused_after_archive(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify an admin key rotation on a stale instance cannot un-archive the developer."""
        # Given a developer loaded before it is archived
        service = DeveloperService()
        developer = await developer_factory()
        stale = await Developer.get(id=developer.id)
        await _admin_set(developer.id, is_archived=True)

        # When a key is generated for the stale instance
        # Then it is refused and the archive holds
        with pytest.raises(NotFoundError):
            await service.generate_api_key(stale)
        refreshed = await Developer.get(id=developer.id)
        assert refreshed.is_archived is True

    async def test_self_update_refused_after_archive(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify a self update on a stale instance cannot un-archive the developer."""
        # Given a developer loaded before a global admin archives it
        service = DeveloperService()
        developer = await developer_factory()
        await service.generate_api_key(developer)
        stale = await Developer.get(id=developer.id)
        await _admin_set(developer.id, is_archived=True)

        # When the developer saves a username change from the stale instance
        # Then the update is refused and nothing changes
        with pytest.raises(NotAuthorizedError):
            await service.update(
                stale,
                DeveloperPatch(username="renamed-after-archive"),
                expected_fingerprint=stale.api_key_fingerprint,
            )
        refreshed = await Developer.get(id=developer.id)
        assert refreshed.is_archived is True
        assert refreshed.username == developer.username

    async def test_self_update_refused_after_admin_rotation(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify a self update is refused once a global admin has rotated the key."""
        # Given a developer loaded before a global admin rotates its key
        service = DeveloperService()
        developer = await developer_factory()
        await service.generate_api_key(developer)
        stale = await Developer.get(id=developer.id)
        admin_copy = await _admin_rotate(developer.id)

        # When the developer saves an email change from the stale instance
        # Then the update is refused and the admin-issued key holds
        with pytest.raises(NotAuthorizedError):
            await service.update(
                stale,
                DeveloperPatch(email="renamed@example.com"),
                expected_fingerprint=stale.api_key_fingerprint,
            )
        refreshed = await Developer.get(id=developer.id)
        assert refreshed.api_key_fingerprint == admin_copy.api_key_fingerprint
        assert refreshed.email == developer.email

    async def test_self_update_keeps_concurrent_demotion(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify a self update writes only its own fields and keeps a concurrent demotion."""
        # Given a global admin developer loaded before it is demoted
        service = DeveloperService()
        developer = await developer_factory(is_global_admin=True)
        await service.generate_api_key(developer)
        stale = await Developer.get(id=developer.id)
        await _admin_set(developer.id, is_global_admin=False)

        # When the developer saves a username change from the stale instance
        await service.update(
            stale,
            DeveloperPatch(username="renamed-after-demote"),
            expected_fingerprint=stale.api_key_fingerprint,
        )

        # Then the username changes and the demotion holds
        refreshed = await Developer.get(id=developer.id)
        assert refreshed.username == "renamed-after-demote"
        assert refreshed.is_global_admin is False
        assert refreshed.date_modified > developer.date_modified

    async def test_admin_update_refused_after_archive(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify an admin update on a stale instance does not write to an archived developer."""
        # Given a developer loaded before it is archived
        service = DeveloperService()
        developer = await developer_factory()
        stale = await Developer.get(id=developer.id)
        await _admin_set(developer.id, is_archived=True)

        # When an admin saves a username change from the stale instance
        # Then it is refused and nothing changes
        with pytest.raises(NotFoundError):
            await service.update(stale, AdminDeveloperPatch(username="renamed-by-admin"))
        refreshed = await Developer.get(id=developer.id)
        assert refreshed.is_archived is True
        assert refreshed.username == developer.username

    async def test_update_diffs_against_locked_row(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify a patch resending the loaded value still overwrites a concurrent change."""
        # Given a developer loaded before an admin renames it
        service = DeveloperService()
        developer = await developer_factory(username="original-name")
        stale = await Developer.get(id=developer.id)
        await _admin_set(developer.id, username="concurrent-name")

        # When an update from the stale instance sets the name it loaded
        changes = await service.update(stale, AdminDeveloperPatch(username="original-name"))

        # Then the patch is applied and audited against the stored value
        refreshed = await Developer.get(id=developer.id)
        assert refreshed.username == "original-name"
        assert changes == {"username": {"old": "concurrent-name", "new": "original-name"}}

    async def test_rotate_reports_live_fingerprint(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify a rotation reports the fingerprint stored at rotation, not at load."""
        # Given a developer loaded before its key is rotated elsewhere
        service = DeveloperService()
        developer = await developer_factory()
        await service.generate_api_key(developer)
        stale = await Developer.get(id=developer.id)
        rotated = await _admin_rotate(developer.id)

        # When an admin rotates the key from the stale instance
        _, previous = await service.rotate_api_key(stale)

        # Then the replaced fingerprint is the one that was live
        assert previous == rotated.api_key_fingerprint


class TestVerifyApiKey:
    """Tests for DeveloperService.verify_api_key."""

    async def test_verify_api_key_success(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify that the correct plaintext key passes verification."""
        # Given a developer with a generated key
        developer = await developer_factory()
        service = DeveloperService()
        key = await service.generate_api_key(developer)

        # When verifying the same key
        result = await service.verify_api_key(developer, key)

        # Then verification succeeds
        assert result is True

    async def test_verify_api_key_failure(
        self, developer_factory: Callable[..., Developer]
    ) -> None:
        """Verify that a wrong key fails verification."""
        # Given a developer with a generated key
        developer = await developer_factory()
        service = DeveloperService()
        await service.generate_api_key(developer)

        # When verifying a different key
        result = await service.verify_api_key(developer, "wrongkeyvalue0000000000000000000")

        # Then verification fails
        assert result is False

    async def test_verify_api_key_no_key(self, developer_factory: Callable[..., Developer]) -> None:
        """Verify that a developer with no stored key always returns False."""
        # Given a developer with no API key set
        developer = await developer_factory()

        # When verifying any key
        result = await DeveloperService().verify_api_key(developer, "somekey")

        # Then verification returns False without error
        assert result is False
