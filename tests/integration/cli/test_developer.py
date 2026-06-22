"""Integration tests for the developer admin CLI command bodies."""

from __future__ import annotations

import pytest

from vapi.cli.developer import _create_developer, _list_developers
from vapi.db.sql_models.developer import Developer

pytestmark = pytest.mark.anyio


class TestCreateDeveloper:
    """Integration tests for _create_developer."""

    async def test_creates_new_developer_with_api_key(self) -> None:
        """Verify a brand-new developer is created and issued an API key."""
        # Given: no developer with this identity exists

        # When: creating a developer
        await _create_developer(email="brand@new.com", username="brand-new", global_admin=False)

        # Then: the developer exists with a hashed API key stored
        dev = await Developer.get_or_none(email="brand@new.com")
        assert dev is not None
        assert dev.username == "brand-new"
        assert dev.hashed_api_key is not None

    async def test_skips_when_email_already_taken(self, developer_factory) -> None:
        """Verify a duplicate email under a different username is skipped, not aborted."""
        # Given: an existing developer owns the email
        await developer_factory(email="taken@example.com", username="original-user")
        before = await Developer.all().count()

        # When: creating a developer that reuses the email with a new username
        await _create_developer(
            email="taken@example.com", username="different-user", global_admin=False
        )

        # Then: no new developer is created and no abort is raised
        assert await Developer.all().count() == before

    async def test_skips_when_username_already_taken(self, developer_factory) -> None:
        """Verify a duplicate username under a different email is skipped, not aborted."""
        # Given: an existing developer owns the username
        await developer_factory(email="original@example.com", username="taken-user")
        before = await Developer.all().count()

        # When: creating a developer that reuses the username with a new email
        await _create_developer(
            email="different@example.com", username="taken-user", global_admin=False
        )

        # Then: no new developer is created and no abort is raised
        assert await Developer.all().count() == before


class TestListDevelopers:
    """Integration tests for _list_developers."""

    async def test_lists_developer_with_company_permission(
        self,
        capsys: pytest.CaptureFixture[str],
        developer_factory,
        company_factory,
        developer_company_permission_factory,
    ) -> None:
        """Verify a developer's company permission is rendered in the listing."""
        # Given: a developer with a company permission
        from vapi.constants import CompanyPermission

        company = await company_factory(name="Acme Co")
        developer = await developer_factory(email="lister@example.com", username="lister")
        await developer_company_permission_factory(
            developer=developer, company=company, permission=CompanyPermission.ADMIN
        )

        # When: listing developers
        await _list_developers()

        # Then: the company name appears in the output
        output = capsys.readouterr().out
        assert "Acme Co" in output
