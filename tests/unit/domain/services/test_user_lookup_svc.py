"""Unit tests for the cross-company user lookup service."""

import pytest

from vapi.constants import CompanyPermission
from vapi.db.sql_models.developer import DeveloperCompanyPermission
from vapi.domain.services.user_lookup_svc import UserLookupService
from vapi.lib.exceptions import ValidationError

pytestmark = pytest.mark.anyio


class TestUserLookupService:
    """Test UserLookupService.lookup()."""

    async def test_lookup_by_email(
        self, company_factory, user_factory, developer_factory, developer_company_permission_factory
    ) -> None:
        """Verify lookup by email returns matches across multiple companies."""
        # Given two companies with the same email user
        company_a = await company_factory(name="Company A", email="a@co.com")
        company_b = await company_factory(name="Company B", email="b@co.com")
        developer = await developer_factory()
        await developer_company_permission_factory(
            developer=developer, company=company_a, permission=CompanyPermission.USER
        )
        await developer_company_permission_factory(
            developer=developer, company=company_b, permission=CompanyPermission.ADMIN
        )
        await user_factory(company=company_a, email="shared@example.com", role="PLAYER")
        await user_factory(company=company_b, email="shared@example.com", role="STORYTELLER")

        # When looking up by email
        results = await UserLookupService().lookup(developer=developer, email="shared@example.com")

        # Then both matches are returned
        assert len(results) == 2
        roles = {r.role for r in results}
        assert roles == {"PLAYER", "STORYTELLER"}
        company_names = {r.company_name for r in results}
        assert company_names == {"Company A", "Company B"}

    async def test_lookup_by_discord_id(
        self, company_factory, user_factory, developer_factory, developer_company_permission_factory
    ) -> None:
        """Verify lookup by discord_id matches against discord_profile JSON."""
        # Given a user with a discord profile
        company = await company_factory(name="Discord Co", email="d@co.com")
        developer = await developer_factory()
        await developer_company_permission_factory(
            developer=developer, company=company, permission=CompanyPermission.USER
        )
        await user_factory(
            company=company,
            email="discord-user@example.com",
            discord_profile={"id": "999888777", "username": "gamer"},
        )

        # When looking up by discord_id
        results = await UserLookupService().lookup(developer=developer, discord_id="999888777")

        # Then the user is found
        assert len(results) == 1
        assert results[0].company_name == "Discord Co"

    async def test_lookup_by_google_id(
        self, company_factory, user_factory, developer_factory, developer_company_permission_factory
    ) -> None:
        """Verify lookup by google_id matches against google_profile JSON."""
        # Given a user with a google profile
        company = await company_factory(name="Google Co", email="g@co.com")
        developer = await developer_factory()
        await developer_company_permission_factory(
            developer=developer, company=company, permission=CompanyPermission.USER
        )
        await user_factory(
            company=company,
            email="google-user@example.com",
            google_profile={"id": "google-abc-123", "email": "google-user@gmail.com"},
        )

        # When looking up by google_id
        results = await UserLookupService().lookup(developer=developer, google_id="google-abc-123")

        # Then the user is found
        assert len(results) == 1
        assert results[0].company_name == "Google Co"

    async def test_lookup_by_github_id(
        self, company_factory, user_factory, developer_factory, developer_company_permission_factory
    ) -> None:
        """Verify lookup by github_id matches against github_profile JSON."""
        # Given a user with a github profile
        company = await company_factory(name="GitHub Co", email="gh@co.com")
        developer = await developer_factory()
        await developer_company_permission_factory(
            developer=developer, company=company, permission=CompanyPermission.USER
        )
        await user_factory(
            company=company,
            email="github-user@example.com",
            github_profile={"id": "gh-456", "login": "octocat"},
        )

        # When looking up by github_id
        results = await UserLookupService().lookup(developer=developer, github_id="gh-456")

        # Then the user is found
        assert len(results) == 1
        assert results[0].company_name == "GitHub Co"

    async def test_lookup_excludes_revoked_companies(
        self, company_factory, user_factory, developer_factory, developer_company_permission_factory
    ) -> None:
        """Verify users on REVOKE'd companies are not returned."""
        # Given a user on a company where the developer's access is revoked
        company = await company_factory(name="Revoked Co", email="r@co.com")
        developer = await developer_factory()
        await developer_company_permission_factory(
            developer=developer, company=company, permission=CompanyPermission.REVOKE
        )
        await user_factory(company=company, email="hidden@example.com")

        # When looking up by email
        results = await UserLookupService().lookup(developer=developer, email="hidden@example.com")

        # Then no results are returned
        assert results == []

    async def test_lookup_global_admin_sees_all_companies(
        self, company_factory, user_factory, developer_factory
    ) -> None:
        """Verify global admin sees users across all companies without explicit permissions."""
        # Given a global admin and a user on a company with no developer permission
        company = await company_factory(name="Any Co", email="any@co.com")
        admin = await developer_factory(is_global_admin=True)
        await user_factory(company=company, email="global@example.com")

        # When looking up by email
        results = await UserLookupService().lookup(developer=admin, email="global@example.com")

        # Then the user is found
        assert len(results) == 1

    async def test_lookup_excludes_archived_users(
        self, company_factory, user_factory, developer_factory, developer_company_permission_factory
    ) -> None:
        """Verify archived users are excluded from results."""
        # Given an archived user
        company = await company_factory(name="Archive Co", email="arch@co.com")
        developer = await developer_factory()
        await developer_company_permission_factory(
            developer=developer, company=company, permission=CompanyPermission.USER
        )
        await user_factory(company=company, email="archived@example.com", is_archived=True)

        # When looking up by email
        results = await UserLookupService().lookup(
            developer=developer, email="archived@example.com"
        )

        # Then no results are returned
        assert results == []

    async def test_lookup_includes_unapproved_users(
        self, company_factory, user_factory, developer_factory, developer_company_permission_factory
    ) -> None:
        """Verify UNAPPROVED users are included in results."""
        # Given an unapproved user
        company = await company_factory(name="Unapproved Co", email="unap@co.com")
        developer = await developer_factory()
        await developer_company_permission_factory(
            developer=developer, company=company, permission=CompanyPermission.USER
        )
        await user_factory(
            company=company, email="unapproved@example.com", role="UNAPPROVED"
        )

        # When looking up by email
        results = await UserLookupService().lookup(
            developer=developer, email="unapproved@example.com"
        )

        # Then the user is found
        assert len(results) == 1
        assert results[0].role == "UNAPPROVED"

    async def test_lookup_includes_deactivated_users(
        self, company_factory, user_factory, developer_factory, developer_company_permission_factory
    ) -> None:
        """Verify DEACTIVATED users are included in results."""
        # Given a deactivated user
        company = await company_factory(name="Deactivated Co", email="deact@co.com")
        developer = await developer_factory()
        await developer_company_permission_factory(
            developer=developer, company=company, permission=CompanyPermission.USER
        )
        await user_factory(
            company=company, email="deactivated@example.com", role="DEACTIVATED"
        )

        # When looking up by email
        results = await UserLookupService().lookup(
            developer=developer, email="deactivated@example.com"
        )

        # Then the user is found
        assert len(results) == 1
        assert results[0].role == "DEACTIVATED"

    async def test_lookup_no_matches_returns_empty_list(
        self, developer_factory
    ) -> None:
        """Verify no matches returns an empty list."""
        # Given a developer with no matching users
        developer = await developer_factory()

        # When looking up a nonexistent email
        results = await UserLookupService().lookup(
            developer=developer, email="nobody@example.com"
        )

        # Then an empty list is returned
        assert results == []

    async def test_lookup_no_identifiers_raises_validation_error(
        self, developer_factory
    ) -> None:
        """Verify providing no identifiers raises ValidationError."""
        # Given a developer
        developer = await developer_factory()

        # When calling lookup with no identifiers
        # Then a ValidationError is raised
        with pytest.raises(ValidationError):
            await UserLookupService().lookup(developer=developer)

    async def test_lookup_multiple_identifiers_raises_validation_error(
        self, developer_factory
    ) -> None:
        """Verify providing multiple identifiers raises ValidationError."""
        # Given a developer
        developer = await developer_factory()

        # When calling lookup with multiple identifiers
        # Then a ValidationError is raised
        with pytest.raises(ValidationError):
            await UserLookupService().lookup(
                developer=developer, email="a@b.com", discord_id="123"
            )
