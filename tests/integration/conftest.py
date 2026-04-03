"""Shared fixtures for integration tests.

Creates developers with real API key credentials so the auth
middleware finds them. All records are created directly in PostgreSQL.
"""

from __future__ import annotations

import pytest

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


@pytest.fixture
async def mirror_company() -> Company:
    """Create a Company for integration tests."""
    company = await Company.create(name="Integration Test Company", email="test@example.com")
    await CompanySettings.create(company=company)
    # Re-fetch to normalize UUID
    return await Company.get(id=str(company.id))


# ---------------------------------------------------------------------------
# Developer fixtures (with API keys for auth)
# ---------------------------------------------------------------------------


@pytest.fixture
async def mirror_global_admin(
    mirror_company: Company,
) -> Developer:
    """Create a global admin Developer with a valid API key."""
    developer, _ = await _create_developer_with_key(
        username="test-global-admin",
        email="global-admin@example.com",
        is_global_admin=True,
    )
    await DeveloperCompanyPermission.create(
        developer=developer,
        company=mirror_company,
        permission=CompanyPermission.OWNER,
    )
    return await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()


@pytest.fixture
async def mirror_company_owner(
    mirror_company: Company,
) -> Developer:
    """Create a company owner Developer with a valid API key."""
    developer, _ = await _create_developer_with_key(
        username="test-company-owner",
        email="owner@example.com",
    )
    await DeveloperCompanyPermission.create(
        developer=developer,
        company=mirror_company,
        permission=CompanyPermission.OWNER,
    )
    return await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()


@pytest.fixture
async def mirror_company_admin(
    mirror_company: Company,
) -> Developer:
    """Create a company admin Developer with a valid API key."""
    developer, _ = await _create_developer_with_key(
        username="test-company-admin",
        email="admin@example.com",
    )
    await DeveloperCompanyPermission.create(
        developer=developer,
        company=mirror_company,
        permission=CompanyPermission.ADMIN,
    )
    return await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()


@pytest.fixture
async def mirror_company_user(
    mirror_company: Company,
) -> Developer:
    """Create a company user Developer with a valid API key."""
    developer, _ = await _create_developer_with_key(
        username="test-company-user",
        email="user-dev@example.com",
    )
    await DeveloperCompanyPermission.create(
        developer=developer,
        company=mirror_company,
        permission=CompanyPermission.USER,
    )
    return await Developer.filter(id=developer.id).prefetch_related("permissions__company").first()


# ---------------------------------------------------------------------------
# Token fixtures (auth headers for HTTP client)
# ---------------------------------------------------------------------------


@pytest.fixture
async def token_global_admin(mirror_global_admin: Developer) -> dict[str, str]:
    """Return auth header for the global admin developer."""
    api_key = await _developer_service.generate_api_key(mirror_global_admin)
    return {AUTH_HEADER_KEY: api_key}


@pytest.fixture
async def token_company_owner(mirror_company_owner: Developer) -> dict[str, str]:
    """Return auth header for the company owner developer."""
    api_key = await _developer_service.generate_api_key(mirror_company_owner)
    return {AUTH_HEADER_KEY: api_key}


@pytest.fixture
async def token_company_admin(mirror_company_admin: Developer) -> dict[str, str]:
    """Return auth header for the company admin developer."""
    api_key = await _developer_service.generate_api_key(mirror_company_admin)
    return {AUTH_HEADER_KEY: api_key}


@pytest.fixture
async def token_company_user(mirror_company_user: Developer) -> dict[str, str]:
    """Return auth header for the company user developer."""
    api_key = await _developer_service.generate_api_key(mirror_company_user)
    return {AUTH_HEADER_KEY: api_key}


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def mirror_user(mirror_company: Company) -> User:
    """Create a User with PLAYER role."""
    user = await User.create(
        username="test-player",
        email="player@example.com",
        role="PLAYER",
        company=mirror_company,
    )
    return await User.filter(id=user.id).prefetch_related("campaign_experiences").first()


@pytest.fixture
async def mirror_user_storyteller(mirror_company: Company) -> User:
    """Create a User with STORYTELLER role."""
    user = await User.create(
        username="test-storyteller",
        email="storyteller@example.com",
        role="STORYTELLER",
        company=mirror_company,
    )
    return await User.filter(id=user.id).prefetch_related("campaign_experiences").first()


@pytest.fixture
async def mirror_user_admin(mirror_company: Company) -> User:
    """Create a User with ADMIN role."""
    user = await User.create(
        username="test-admin-user",
        email="admin-user@example.com",
        role="ADMIN",
        company=mirror_company,
    )
    return await User.filter(id=user.id).prefetch_related("campaign_experiences").first()


# ---------------------------------------------------------------------------
# Campaign fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def mirror_campaign(mirror_company: Company) -> Campaign:
    """Create a Campaign."""
    campaign = await Campaign.create(name="Integration Campaign", company=mirror_company)
    return await Campaign.get(id=str(campaign.id))


@pytest.fixture
async def mirror_campaign_book(mirror_campaign: Campaign) -> CampaignBook:
    """Create a CampaignBook."""
    book = await CampaignBook.create(name="Integration Book", number=1, campaign=mirror_campaign)
    return await CampaignBook.get(id=str(book.id))


@pytest.fixture
async def mirror_campaign_chapter(mirror_campaign_book: CampaignBook) -> CampaignChapter:
    """Create a CampaignChapter."""
    chapter = await CampaignChapter.create(
        name="Integration Chapter", number=1, book=mirror_campaign_book
    )
    return await CampaignChapter.get(id=str(chapter.id))
