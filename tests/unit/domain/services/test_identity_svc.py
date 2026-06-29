"""Tests for the identity resolution service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.fixtures import build_verified_identity as _identity
from vapi.constants import IdentityProvider, UserRole
from vapi.db.sql_models.user import User
from vapi.domain.services.identity_svc import IdentityResolution, IdentityService
from vapi.lib.exceptions import ConflictError, NotFoundError, UnprocessableEntityError

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.sql_models.company import Company

pytestmark = pytest.mark.anyio


class TestResolve:
    """Test IdentityService.resolve."""

    async def test_match_by_provider_id(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify an existing user with the provider ID is matched."""
        # Given a user already carrying this apple identity
        company = await company_factory()
        user = await user_factory(
            company=company, apple_profile={"id": "apple-sub-001", "email": "old@example.com"}
        )

        # When the identity is resolved
        service = IdentityService()
        resolved, resolution, _ = await service.resolve(company=company, identity=_identity())

        # Then the existing user is matched and the profile refreshed
        assert resolution == IdentityResolution.MATCHED
        assert resolved.id == user.id
        assert resolved.apple_profile["email"] == "person@example.com"

    async def test_match_unchanged_profile_reports_not_modified(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify a matched login whose stored profile is identical reports no modification."""
        # Given a user whose stored profile already equals the verified profile
        company = await company_factory()
        await user_factory(
            company=company,
            apple_profile={"id": "apple-sub-001", "email": "person@example.com"},
        )

        # When the identity is resolved
        service = IdentityService()
        _, resolution, user_modified = await service.resolve(company=company, identity=_identity())

        # Then it matches but reports the row was not modified (so callers can skip invalidation)
        assert resolution == IdentityResolution.MATCHED
        assert user_modified is False

    async def test_match_changed_profile_reports_modified(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify a matched login that refreshes a changed profile reports modification."""
        # Given a user whose stored profile differs from the verified profile
        company = await company_factory()
        await user_factory(
            company=company,
            apple_profile={"id": "apple-sub-001", "email": "old@example.com"},
        )

        # When the identity is resolved
        service = IdentityService()
        resolved, resolution, user_modified = await service.resolve(
            company=company, identity=_identity()
        )

        # Then it matches, reports the row was modified, and the profile is refreshed
        assert resolution == IdentityResolution.MATCHED
        assert user_modified is True
        assert resolved.apple_profile["email"] == "person@example.com"

    async def test_auto_link_by_verified_email(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify a verified-email match links the new provider to the existing user."""
        # Given a user with the same email but no apple identity
        company = await company_factory()
        user = await user_factory(company=company, email="person@example.com")

        # When the identity is resolved
        service = IdentityService()
        resolved, resolution, _ = await service.resolve(company=company, identity=_identity())

        # Then the identity is linked onto the existing user
        assert resolution == IdentityResolution.LINKED
        assert resolved.id == user.id
        assert resolved.apple_profile["id"] == "apple-sub-001"

        # Then the profile is persisted to the database
        persisted = await User.get(id=resolved.id)
        assert persisted.apple_profile["id"] == "apple-sub-001"

    async def test_unverified_email_does_not_link(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify an unverified email never auto-links."""
        # Given a user with a matching email but an unverified provider email
        company = await company_factory()
        existing = await user_factory(company=company, email="person@example.com")

        # When the identity is resolved
        service = IdentityService()
        resolved, resolution, _ = await service.resolve(
            company=company, identity=_identity(email_verified=False)
        )

        # Then a fresh user is created instead
        assert resolution == IdentityResolution.CREATED
        assert resolved.id != existing.id

    async def test_ambiguous_email_falls_through_to_create(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify an email matching multiple users skips auto-link."""
        # Given two users sharing the email
        company = await company_factory()
        await user_factory(company=company, email="person@example.com")
        await user_factory(company=company, email="person@example.com")

        # When the identity is resolved
        service = IdentityService()
        resolved, resolution, _ = await service.resolve(company=company, identity=_identity())

        # Then a fresh user is created
        assert resolution == IdentityResolution.CREATED
        assert resolved.apple_profile["id"] == "apple-sub-001"

    async def test_archived_user_never_matched(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify archived users are never matched or resurrected."""
        # Given an archived user carrying the provider ID and email
        company = await company_factory()
        archived = await user_factory(
            company=company,
            email="person@example.com",
            apple_profile={"id": "apple-sub-001"},
            is_archived=True,
        )

        # When the identity is resolved
        service = IdentityService()
        resolved, resolution, _ = await service.resolve(company=company, identity=_identity())

        # Then a fresh user is created
        assert resolution == IdentityResolution.CREATED
        assert resolved.id != archived.id

    async def test_deactivated_user_still_matches(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify a DEACTIVATED user still matches by provider ID (identity is real)."""
        # Given a deactivated user carrying the provider ID
        company = await company_factory()
        user = await user_factory(
            company=company, role="DEACTIVATED", apple_profile={"id": "apple-sub-001"}
        )

        # When the identity is resolved
        service = IdentityService()
        resolved, resolution, _ = await service.resolve(company=company, identity=_identity())

        # Then the deactivated user is matched with their status visible
        assert resolution == IdentityResolution.MATCHED
        assert resolved.id == user.id
        assert resolved.role == UserRole.DEACTIVATED

    async def test_create_new_unapproved_user(
        self, company_factory: Callable[..., Company]
    ) -> None:
        """Verify an unknown identity creates an UNAPPROVED user."""
        # Given an empty company
        company = await company_factory()

        # When the identity is resolved with an explicit username
        service = IdentityService()
        resolved, resolution, _ = await service.resolve(
            company=company, identity=_identity(), username="chosen-name"
        )

        # Then a new UNAPPROVED user exists with the verified profile
        assert resolution == IdentityResolution.CREATED
        assert resolved.role == UserRole.UNAPPROVED
        assert resolved.username == "chosen-name"
        assert resolved.email == "person@example.com"
        assert resolved.apple_profile["id"] == "apple-sub-001"

        # Then the profile is persisted to the database
        persisted = await User.get(id=resolved.id)
        assert persisted.apple_profile["id"] == "apple-sub-001"

    async def test_username_derivation_and_collision(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify usernames are derived from the profile with collision suffixes."""
        # Given a user already holding the derived username
        company = await company_factory()
        await user_factory(company=company, username="octocat")

        # When a github identity with login octocat is resolved
        service = IdentityService()
        resolved, resolution, _ = await service.resolve(
            company=company,
            identity=_identity(
                provider="github",
                provider_id="4242",
                profile={"id": "4242", "login": "octocat", "email": "person2@example.com"},
                email="person2@example.com",
            ),
        )

        # Then the username gets a collision suffix
        assert resolution == IdentityResolution.CREATED
        assert resolved.username == "octocat-2"

    async def test_create_without_email_raises(
        self, company_factory: Callable[..., Company]
    ) -> None:
        """Verify creation without any email raises 422."""
        # Given an identity with no email and no fallback
        company = await company_factory()

        # When the identity is resolved
        # Then resolution fails with the EMAIL_REQUIRED error code
        service = IdentityService()
        with pytest.raises(UnprocessableEntityError) as exc_info:
            await service.resolve(
                company=company, identity=_identity(email=None, email_verified=False)
            )
        assert exc_info.value.extension == {"code": "EMAIL_REQUIRED"}

    async def test_create_with_fallback_email(
        self, company_factory: Callable[..., Company]
    ) -> None:
        """Verify a client-supplied fallback email is used when the provider has none."""
        # Given an identity with no provider email
        company = await company_factory()

        # When resolved with a fallback email
        service = IdentityService()
        resolved, resolution, _ = await service.resolve(
            company=company,
            identity=_identity(email=None, email_verified=False),
            fallback_email="fallback@example.com",
        )

        # Then the user is created with the fallback email
        assert resolution == IdentityResolution.CREATED
        assert resolved.email == "fallback@example.com"

    async def test_auto_link_onto_deactivated_user(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify auto-link attaches to a deactivated user rather than creating a duplicate."""
        # Given a deactivated user with the matching verified email
        company = await company_factory()
        user = await user_factory(company=company, email="person@example.com", role="DEACTIVATED")

        # When the identity is resolved
        service = IdentityService()
        resolved, resolution, _ = await service.resolve(company=company, identity=_identity())

        # Then the identity links to the deactivated account with the status visible
        assert resolution == IdentityResolution.LINKED
        assert resolved.id == user.id
        assert resolved.role == UserRole.DEACTIVATED

    async def test_auto_link_case_insensitive_email(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify auto-link matches regardless of email address case."""
        # Given a user whose stored email has mixed case
        company = await company_factory()
        user = await user_factory(company=company, email="Person@Example.com")

        # When an identity arrives with the same address in lower case
        service = IdentityService()
        resolved, resolution, _ = await service.resolve(company=company, identity=_identity())

        # Then the identity links onto the existing user
        assert resolution == IdentityResolution.LINKED
        assert resolved.id == user.id


class TestLinkIdentity:
    """Test IdentityService.link_identity."""

    async def test_link_success(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify a verified identity is attached to the user."""
        # Given a user without an apple identity
        company = await company_factory()
        user = await user_factory(company=company)

        # When the identity is linked
        service = IdentityService()
        linked = await service.link_identity(company=company, user=user, identity=_identity())

        # Then the profile is attached and persisted
        assert linked.apple_profile["id"] == "apple-sub-001"
        persisted = await User.get(id=user.id)
        assert persisted.apple_profile["id"] == "apple-sub-001"

    async def test_link_idempotent_same_provider_id(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify re-linking the same provider ID refreshes the profile."""
        # Given a user already linked to this apple identity
        company = await company_factory()
        user = await user_factory(
            company=company, apple_profile={"id": "apple-sub-001", "email": "old@example.com"}
        )

        # When the identity is linked again
        service = IdentityService()
        linked = await service.link_identity(company=company, user=user, identity=_identity())

        # Then the profile is refreshed without error
        assert linked.apple_profile["email"] == "person@example.com"

    async def test_link_conflict_other_user(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify linking an identity owned by another user raises 409."""
        # Given another user already holding this apple identity
        company = await company_factory()
        await user_factory(company=company, apple_profile={"id": "apple-sub-001"})
        user = await user_factory(company=company)

        # When the identity is linked
        # Then a conflict is raised with the error code
        service = IdentityService()
        with pytest.raises(ConflictError) as exc_info:
            await service.link_identity(company=company, user=user, identity=_identity())
        assert exc_info.value.extension == {"code": "IDENTITY_ALREADY_LINKED"}

    async def test_link_conflict_different_provider_id(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify linking over an existing different identity raises 409."""
        # Given a user already linked to a different apple identity
        company = await company_factory()
        user = await user_factory(company=company, apple_profile={"id": "other-sub"})

        # When the identity is linked
        # Then a conflict is raised (no silent overwrite)
        service = IdentityService()
        with pytest.raises(ConflictError) as exc_info:
            await service.link_identity(company=company, user=user, identity=_identity())
        assert exc_info.value.extension == {"code": "IDENTITY_ALREADY_LINKED"}


class TestUnlinkIdentity:
    """Test IdentityService.unlink_identity."""

    async def test_unlink_success(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify a linked identity is removed when the user has another remaining."""
        # Given a user with two linked identities
        company = await company_factory()
        user = await user_factory(
            company=company,
            apple_profile={"id": "apple-sub-001"},
            github_profile={"id": "4242"},
        )

        # When the apple identity is unlinked
        service = IdentityService()
        unlinked = await service.unlink_identity(user=user, provider=IdentityProvider.APPLE)

        # Then the apple profile is cleared and the github profile remains
        assert unlinked.apple_profile is None
        assert unlinked.github_profile == {"id": "4242"}
        persisted = await User.get(id=user.id)
        assert persisted.apple_profile is None
        assert persisted.github_profile == {"id": "4242"}

    async def test_unlink_not_linked_raises(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify unlinking a provider the user never linked raises 404."""
        # Given a user with only an apple identity
        company = await company_factory()
        user = await user_factory(company=company, apple_profile={"id": "apple-sub-001"})

        # When the unlinked github identity is removed
        # Then a not-found error is raised with the error code
        service = IdentityService()
        with pytest.raises(NotFoundError) as exc_info:
            await service.unlink_identity(user=user, provider=IdentityProvider.GITHUB)
        assert exc_info.value.extension == {"code": "IDENTITY_NOT_LINKED"}

    async def test_unlink_last_identity_raises(
        self, company_factory: Callable[..., Company], user_factory: Callable[..., User]
    ) -> None:
        """Verify removing the user's only identity is refused."""
        # Given a user with a single linked identity
        company = await company_factory()
        user = await user_factory(company=company, apple_profile={"id": "apple-sub-001"})

        # When that sole identity is unlinked
        # Then a conflict is raised and the profile is left untouched
        service = IdentityService()
        with pytest.raises(ConflictError) as exc_info:
            await service.unlink_identity(user=user, provider=IdentityProvider.APPLE)
        assert exc_info.value.extension == {"code": "LAST_IDENTITY"}
        persisted = await User.get(id=user.id)
        assert persisted.apple_profile == {"id": "apple-sub-001"}
