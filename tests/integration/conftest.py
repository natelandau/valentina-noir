"""Shared fixtures for integration tests.

Creates developers with real API key credentials so the auth
middleware finds them. All records are created directly in PostgreSQL.
"""

from __future__ import annotations

import pytest

from tests.conftest import register_session_id
from vapi.constants import AUTH_HEADER_KEY, CompanyPermission
from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.company import Company, CompanySettings
from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.db.sql_models.user import User
from vapi.domain.services.developer_svc import DeveloperService

pytestmark = pytest.mark.anyio

_developer_service = DeveloperService()


async def _create_developer_with_key(
    *,
    username: str,
    email: str,
    is_global_admin: bool = False,
) -> tuple[Developer, str]:
    """Create a Developer and generate an API key.

    Returns:
        Tuple of (developer, plaintext_api_key).
    """
    developer = await Developer.create(
        username=username,
        email=email,
        is_global_admin=is_global_admin,
    )
    api_key = await _developer_service.generate_api_key(developer)
    developer = (
        await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()
    )
    return developer, api_key


# ---------------------------------------------------------------------------
# Company fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def session_company() -> Company:
    """Create a Company for integration tests.

    Session-scoped: created once and preserved across per-test cleanup.
    """
    company = await Company.create(name="Integration Test Company", email="test@example.com")
    cs = await CompanySettings.create(company=company)
    company = await Company.get(id=str(company.id))
    register_session_id('"company"', str(company.id))
    register_session_id('"company_settings"', str(cs.id))
    return company


# ---------------------------------------------------------------------------
# Developer fixtures (with API keys for auth)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def session_global_admin(
    session_company: Company,
) -> Developer:
    """Create a global admin Developer with a valid API key.

    Session-scoped: created once and preserved across per-test cleanup.
    """
    developer, _ = await _create_developer_with_key(
        username="test-global-admin",
        email="global-admin@example.com",
        is_global_admin=True,
    )
    perm = await DeveloperCompanyPermission.create(
        developer=developer,
        company=session_company,
        permission=CompanyPermission.OWNER,
    )
    register_session_id('"developer"', str(developer.id))
    register_session_id('"developer_company_permission"', str(perm.id))
    return await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()


@pytest.fixture(scope="session")
async def session_company_owner(
    session_company: Company,
) -> Developer:
    """Create a company owner Developer with a valid API key.

    Session-scoped: created once and preserved across per-test cleanup.
    """
    developer, _ = await _create_developer_with_key(
        username="test-company-owner",
        email="owner@example.com",
    )
    perm = await DeveloperCompanyPermission.create(
        developer=developer,
        company=session_company,
        permission=CompanyPermission.OWNER,
    )
    register_session_id('"developer"', str(developer.id))
    register_session_id('"developer_company_permission"', str(perm.id))
    return await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()


@pytest.fixture(scope="session")
async def session_company_admin(
    session_company: Company,
) -> Developer:
    """Create a company admin Developer with a valid API key.

    Session-scoped: created once and preserved across per-test cleanup.
    """
    developer, _ = await _create_developer_with_key(
        username="test-company-admin",
        email="admin@example.com",
    )
    perm = await DeveloperCompanyPermission.create(
        developer=developer,
        company=session_company,
        permission=CompanyPermission.ADMIN,
    )
    register_session_id('"developer"', str(developer.id))
    register_session_id('"developer_company_permission"', str(perm.id))
    return await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()


@pytest.fixture(scope="session")
async def session_company_user(
    session_company: Company,
) -> Developer:
    """Create a company user Developer with a valid API key.

    Session-scoped: created once and preserved across per-test cleanup.
    """
    developer, _ = await _create_developer_with_key(
        username="test-company-user",
        email="user-dev@example.com",
    )
    perm = await DeveloperCompanyPermission.create(
        developer=developer,
        company=session_company,
        permission=CompanyPermission.USER,
    )
    register_session_id('"developer"', str(developer.id))
    register_session_id('"developer_company_permission"', str(perm.id))
    return await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()


# ---------------------------------------------------------------------------
# Token fixtures (auth headers for HTTP client)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def token_global_admin(session_global_admin: Developer) -> dict[str, str]:
    """Return auth header for the global admin developer."""
    api_key = await _developer_service.generate_api_key(session_global_admin)
    return {AUTH_HEADER_KEY: api_key}


@pytest.fixture(scope="session")
async def token_company_owner(session_company_owner: Developer) -> dict[str, str]:
    """Return auth header for the company owner developer."""
    api_key = await _developer_service.generate_api_key(session_company_owner)
    return {AUTH_HEADER_KEY: api_key}


@pytest.fixture(scope="session")
async def token_company_admin(session_company_admin: Developer) -> dict[str, str]:
    """Return auth header for the company admin developer."""
    api_key = await _developer_service.generate_api_key(session_company_admin)
    return {AUTH_HEADER_KEY: api_key}


@pytest.fixture(scope="session")
async def token_company_user(session_company_user: Developer) -> dict[str, str]:
    """Return auth header for the company user developer."""
    api_key = await _developer_service.generate_api_key(session_company_user)
    return {AUTH_HEADER_KEY: api_key}


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def session_user(session_company: Company) -> User:
    """Create a User with PLAYER role.

    Session-scoped: created once and preserved across per-test cleanup.
    """
    user = await User.create(
        username="test-player",
        email="player@example.com",
        role="PLAYER",
        company=session_company,
    )
    register_session_id('"user"', str(user.id))
    return await User.filter(id=user.id).prefetch_related("campaign_experiences").first()


@pytest.fixture(scope="session")
async def session_user_storyteller(session_company: Company) -> User:
    """Create a User with STORYTELLER role.

    Session-scoped: created once and preserved across per-test cleanup.
    """
    user = await User.create(
        username="test-storyteller",
        email="storyteller@example.com",
        role="STORYTELLER",
        company=session_company,
    )
    register_session_id('"user"', str(user.id))
    return await User.filter(id=user.id).prefetch_related("campaign_experiences").first()


@pytest.fixture(scope="session")
async def session_user_admin(session_company: Company) -> User:
    """Create a User with ADMIN role.

    Session-scoped: created once and preserved across per-test cleanup.
    """
    user = await User.create(
        username="test-admin-user",
        email="admin-user@example.com",
        role="ADMIN",
        company=session_company,
    )
    register_session_id('"user"', str(user.id))
    return await User.filter(id=user.id).prefetch_related("campaign_experiences").first()


@pytest.fixture(scope="session")
async def session_acting_user(session_company: Company) -> User:
    """Create a default acting user (ADMIN) for the On-Behalf-Of header.

    Session-scoped: created once and preserved across per-test cleanup.
    Most integration tests use this as the default acting user. Tests
    that need specific roles create their own users via factories.
    """
    user = await User.create(
        username="test-acting-user",
        email="acting-user@example.com",
        role="ADMIN",
        company=session_company,
    )
    register_session_id('"user"', str(user.id))
    return await User.filter(id=user.id).prefetch_related("campaign_experiences").first()


@pytest.fixture(scope="session")
def on_behalf_of_header(session_acting_user: User) -> dict[str, str]:
    """Return the On-Behalf-Of header for the default acting user.

    Merge with auth token headers in tests:
        headers = token_company_user | on_behalf_of_header
    """
    return {"On-Behalf-Of": str(session_acting_user.id)}


# ---------------------------------------------------------------------------
# Campaign fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
async def session_campaign(session_company: Company) -> Campaign:
    """Create a Campaign.

    Session-scoped: created once and preserved across per-test cleanup.
    """
    campaign = await Campaign.create(name="Integration Campaign", company=session_company)
    campaign = await Campaign.get(id=str(campaign.id))
    register_session_id('"campaign"', str(campaign.id))
    return campaign


@pytest.fixture(scope="session")
async def session_campaign_book(session_campaign: Campaign) -> CampaignBook:
    """Create a CampaignBook.

    Session-scoped: created once and preserved across per-test cleanup.
    """
    book = await CampaignBook.create(name="Integration Book", number=1, campaign=session_campaign)
    book = await CampaignBook.get(id=str(book.id))
    register_session_id('"campaign_book"', str(book.id))
    return book


@pytest.fixture(scope="session")
async def session_campaign_chapter(session_campaign_book: CampaignBook) -> CampaignChapter:
    """Create a CampaignChapter.

    Session-scoped: created once and preserved across per-test cleanup.
    """
    chapter = await CampaignChapter.create(
        name="Integration Chapter", number=1, book=session_campaign_book
    )
    chapter = await CampaignChapter.get(id=str(chapter.id))
    register_session_id('"campaign_chapter"', str(chapter.id))
    return chapter
