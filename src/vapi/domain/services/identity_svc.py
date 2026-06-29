"""Identity resolution service.

Resolves a VerifiedIdentity (a provider credential the API has already
cryptographically verified) to a canonical user: match by provider ID,
auto-link by verified email, or create a new UNAPPROVED user.
"""

from enum import StrEnum
from typing import TYPE_CHECKING

from tortoise.expressions import RawSQL

from vapi.constants import PROVIDER_PROFILE_FIELDS, IdentityProvider, UserRole
from vapi.db.sql_models.user import User
from vapi.lib.exceptions import ConflictError, NotFoundError, UnprocessableEntityError
from vapi.utils.strings import random_string

if TYPE_CHECKING:
    from vapi.db.sql_models.company import Company
    from vapi.utils.identity import VerifiedIdentity

# User.username has a MinLengthValidator(3); derived bases shorter than this get a suffix
MIN_USERNAME_LENGTH = 3


class IdentityResolution(StrEnum):
    """How an identity call resolved to a user."""

    MATCHED = "matched"
    LINKED = "linked"
    CREATED = "created"


class IdentityService:
    """Resolve verified provider identities to canonical users."""

    @staticmethod
    async def _find_by_provider_id(
        *, company: "Company", profile_field: str, provider_id: str
    ) -> User | None:
        """Find the non-archived company user holding this provider ID.

        Args:
            company: The company to search within.
            profile_field: The JSON column name (e.g. "apple_profile").
            provider_id: The provider-issued subject identifier.
        """
        # profile_field comes from PROVIDER_PROFILE_FIELDS, never from user input
        return (
            await User.filter(company_id=company.id, is_archived=False)
            .annotate(_provider_id=RawSQL(f"{profile_field}->>'id'"))
            .filter(_provider_id=provider_id)
            .prefetch_related("campaign_experiences")
            .first()
        )

    async def resolve(
        self,
        *,
        company: "Company",
        identity: "VerifiedIdentity",
        username: str | None = None,
        fallback_email: str | None = None,
    ) -> tuple[User, IdentityResolution, bool]:
        """Resolve a verified identity: match, auto-link, or create.

        Attempts resolution in priority order: provider-ID match first,
        then verified-email auto-link, then new-user creation. Archived
        users are never matched or resurrected regardless of their credentials.

        Args:
            company: The company to resolve within.
            identity: The verified provider identity.
            username: Optional username, used only when a new user is created.
            fallback_email: Client-supplied email, used only on create when the
                provider supplied none. Never used for auto-link matching.

        Returns:
            The resolved user, how it was resolved, and whether the user row was
            modified. A matched login whose stored profile already equals the
            verified profile changes nothing, so callers can skip cache
            invalidation for it; creates and links always report modified.

        Raises:
            UnprocessableEntityError: Creation is needed but no email is available.

        Note:
            Concurrent resolves for a brand-new identity share the same
            check-then-act window as the register endpoint and can create
            duplicate UNAPPROVED users. The merge endpoint is the repair path.
        """
        profile_field = PROVIDER_PROFILE_FIELDS[IdentityProvider(identity.provider)]

        user = await self._find_by_provider_id(
            company=company, profile_field=profile_field, provider_id=identity.provider_id
        )
        if user:
            # Only write when the verified profile actually differs; an unchanged
            # login must leave the row (and its auto_now date_modified) untouched so
            # the caller can safely skip cache invalidation for a routine login.
            user_modified = getattr(user, profile_field) != identity.profile
            if user_modified:
                setattr(user, profile_field, identity.profile)
                await user.save()
            return user, IdentityResolution.MATCHED, user_modified

        # Auto-link only on provider-verified emails; client assertions never link
        if identity.email and identity.email_verified:
            # Intentionally does NOT exclude DEACTIVATED users: skipping them
            # would route the login to a fresh UNAPPROVED account with the same
            # email, creating a duplicate that bypasses deactivation if an admin
            # later approves it. Linking keeps the identity unified while role
            # guards still block the user from acting.
            matches = await User.filter(
                company_id=company.id, email__iexact=identity.email, is_archived=False
            )
            if len(matches) == 1:
                user = matches[0]
                setattr(user, profile_field, identity.profile)
                await user.save()
                await user.fetch_related("campaign_experiences")
                return user, IdentityResolution.LINKED, True

        user = await self._create_user(
            company=company,
            identity=identity,
            profile_field=profile_field,
            username=username,
            fallback_email=fallback_email,
        )
        return user, IdentityResolution.CREATED, True

    async def link_identity(
        self, *, company: "Company", user: User, identity: "VerifiedIdentity"
    ) -> User:
        """Attach an additional verified provider identity to a user.

        Args:
            company: The company scope for conflict checks.
            user: The user receiving the identity.
            identity: The verified provider identity to attach.

        Returns:
            The updated user.

        Raises:
            ConflictError: The identity belongs to another user, or the user
                already has a different identity from this provider.
        """
        profile_field = PROVIDER_PROFILE_FIELDS[IdentityProvider(identity.provider)]

        existing = await self._find_by_provider_id(
            company=company, profile_field=profile_field, provider_id=identity.provider_id
        )
        if existing and existing.id != user.id:
            raise ConflictError(
                detail=(
                    "This identity is already linked to another user. "
                    "Use the merge endpoint to combine accounts."
                ),
                code="IDENTITY_ALREADY_LINKED",
            )

        current = getattr(user, profile_field) or {}
        if current.get("id") and str(current["id"]) != identity.provider_id:
            raise ConflictError(
                detail=f"User already has a different {identity.provider} identity linked.",
                code="IDENTITY_ALREADY_LINKED",
            )

        setattr(user, profile_field, identity.profile)
        await user.save()
        await user.fetch_related("campaign_experiences")
        return user

    async def unlink_identity(self, *, user: User, provider: IdentityProvider) -> User:
        """Remove a linked provider identity from a user.

        Use this for "disconnect account" settings flows. The user's last
        remaining identity is protected so unlinking can never leave an account
        with no way to authenticate.

        Args:
            user: The user to remove the identity from.
            provider: The provider whose identity to remove.

        Returns:
            The updated user.

        Raises:
            NotFoundError: The user has no identity from this provider.
            ConflictError: The identity is the user's only linked identity.
        """
        profile_field = PROVIDER_PROFILE_FIELDS[provider]
        # A linked identity is a non-null JSON column; compare to None rather than
        # truthiness so an empty-dict profile still counts as linked.
        if getattr(user, profile_field) is None:
            raise NotFoundError(
                detail=f"No {provider.value} identity is linked to this user.",
                code="IDENTITY_NOT_LINKED",
            )

        linked_count = sum(
            1 for field in PROVIDER_PROFILE_FIELDS.values() if getattr(user, field) is not None
        )
        if linked_count <= 1:
            raise ConflictError(
                detail="Cannot remove the user's only linked identity.",
                code="LAST_IDENTITY",
            )

        setattr(user, profile_field, None)
        await user.save()
        await user.fetch_related("campaign_experiences")
        return user

    async def _create_user(
        self,
        *,
        company: "Company",
        identity: "VerifiedIdentity",
        profile_field: str,
        username: str | None,
        fallback_email: str | None,
    ) -> User:
        """Create a new UNAPPROVED user for an unmatched identity.

        Args:
            company: The company to create the user within.
            identity: The verified provider identity.
            profile_field: The JSON column to write the provider profile into.
            username: Caller-supplied username; derived from profile when absent.
            fallback_email: Client-supplied email when the provider carries none.

        Raises:
            UnprocessableEntityError: No email is available from either source.
        """
        email = identity.email or fallback_email
        if not email:
            raise UnprocessableEntityError(
                detail=(
                    f"{identity.provider} did not supply an email address. "
                    "Include 'email' in the request body to register this user."
                ),
                code="EMAIL_REQUIRED",
            )

        resolved_username = username or await self._derive_username(
            company=company, identity=identity
        )
        # Build the unsaved instance first so the provider profile can be set via
        # setattr before the single INSERT, avoiding the INSERT+UPDATE two-round-trip
        # pattern that User.create() + save() would produce.
        user = User(
            username=resolved_username,
            email=email,
            role=UserRole.UNAPPROVED,
            company_id=company.id,
        )
        setattr(user, profile_field, identity.profile)
        await user.save()
        await user.fetch_related("campaign_experiences")
        return user

    @staticmethod
    async def _derive_username(*, company: "Company", identity: "VerifiedIdentity") -> str:
        """Derive a unique username from the verified profile.

        Prefers login/username fields from the profile, then the local part of
        the email, then a random fallback. Appends a numeric suffix on collision.

        Args:
            company: The company to check for username uniqueness within.
            identity: The verified provider identity.
        """
        profile = identity.profile
        base: str = (
            profile.get("login")
            or profile.get("username")
            or (identity.email.split("@")[0] if identity.email else None)
            or f"user-{random_string(8).lower()}"
        )
        # Username validator requires at least MIN_USERNAME_LENGTH characters
        if len(base) < MIN_USERNAME_LENGTH:
            base = f"{base}-{random_string(4).lower()}"
        base = base[:50]

        candidate = base
        suffix = 1
        while await User.filter(
            company_id=company.id, username=candidate, is_archived=False
        ).exists():
            suffix += 1
            candidate = f"{base[:46]}-{suffix}"
        return candidate
