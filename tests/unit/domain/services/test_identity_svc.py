"""Tests for the identity resolution service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from vapi.constants import UserRole
from vapi.db.sql_models.user import User
from vapi.domain.services.identity_svc import IdentityResolution, IdentityService
from vapi.lib.exceptions import UnprocessableEntityError
from vapi.utils.identity import VerifiedIdentity

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.sql_models.company import Company

pytestmark = pytest.mark.anyio


def _identity(**overrides: Any) -> VerifiedIdentity:
    """Build a VerifiedIdentity with sensible defaults."""
    defaults: dict[str, Any] = {
        "provider": "apple",
        "provider_id": "apple-sub-001",
        "email": "person@example.com",
        "email_verified": True,
        "profile": {"id": "apple-sub-001", "email": "person@example.com"},
    }
    defaults.update(overrides)
    return VerifiedIdentity(**defaults)


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
        resolved, resolution = await service.resolve(company=company, identity=_identity())

        # Then the existing user is matched and the profile refreshed
        assert resolution == IdentityResolution.MATCHED
        assert resolved.id == user.id
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
        resolved, resolution = await service.resolve(company=company, identity=_identity())

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
        resolved, resolution = await service.resolve(
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
        resolved, resolution = await service.resolve(company=company, identity=_identity())

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
        resolved, resolution = await service.resolve(company=company, identity=_identity())

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
        resolved, resolution = await service.resolve(company=company, identity=_identity())

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
        resolved, resolution = await service.resolve(
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
        resolved, resolution = await service.resolve(
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
        resolved, resolution = await service.resolve(
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
        resolved, resolution = await service.resolve(company=company, identity=_identity())

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
        resolved, resolution = await service.resolve(company=company, identity=_identity())

        # Then the identity links onto the existing user
        assert resolution == IdentityResolution.LINKED
        assert resolved.id == user.id
