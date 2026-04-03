"""Shared fixtures for domain integration tests that use Tortoise-based controllers.

The auth middleware queries Tortoise Developer by API key fingerprint. Integration
tests create Beanie developers (via fixture_models.py) that only exist in MongoDB.
The bridge creates matching Tortoise developers with the same API key credentials
so auth and guards work natively — no monkeypatching needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from vapi.constants import CompanyPermission
from vapi.db.sql_models.campaign import Campaign as PgCampaign
from vapi.db.sql_models.campaign import CampaignBook as PgCampaignBook
from vapi.db.sql_models.campaign import CampaignChapter as PgCampaignChapter
from vapi.db.sql_models.company import Company as PgCompany
from vapi.db.sql_models.company import CompanySettings as PgCompanySettings
from vapi.db.sql_models.developer import Developer as PgDeveloper
from vapi.db.sql_models.developer import DeveloperCompanyPermission
from vapi.db.sql_models.user import User as PgUser

if TYPE_CHECKING:
    from vapi.db.models import Company, Developer

pytestmark = pytest.mark.anyio

# Module-level mapping from Beanie developer ID (str) to Tortoise developer object
_BEANIE_TO_PG_DEVELOPER: dict[str, PgDeveloper] = {}
_BEANIE_COMPANY_TO_PG_COMPANY: dict[str, PgCompany] = {}
_BEANIE_USER_TO_PG_USER: dict[str, PgUser] = {}


@pytest.fixture
def _clear_bridge_maps() -> None:
    """Clear bridge mappings before each test."""
    _BEANIE_TO_PG_DEVELOPER.clear()
    _BEANIE_COMPANY_TO_PG_COMPANY.clear()
    _BEANIE_USER_TO_PG_USER.clear()
    yield
    _BEANIE_TO_PG_DEVELOPER.clear()
    _BEANIE_COMPANY_TO_PG_COMPANY.clear()
    _BEANIE_USER_TO_PG_USER.clear()


@pytest.fixture
async def pg_mirror_company(
    base_company: Company,
    _clear_bridge_maps: None,
    _patch_pg_bridge: None,
) -> PgCompany:
    """Return the Tortoise Company created by the bridge."""
    return _BEANIE_COMPANY_TO_PG_COMPANY[str(base_company.id)]


@pytest.fixture
async def pg_mirror_global_admin(
    base_developer_global_admin: Developer,
    pg_mirror_company: PgCompany,
) -> PgDeveloper:
    """Return the Tortoise Developer created by the bridge."""
    return _BEANIE_TO_PG_DEVELOPER[str(base_developer_global_admin.id)]


@pytest.fixture
async def pg_mirror_company_owner(
    base_developer_company_owner: Developer,
    pg_mirror_company: PgCompany,
) -> PgDeveloper:
    """Return the Tortoise Developer created by the bridge."""
    return _BEANIE_TO_PG_DEVELOPER[str(base_developer_company_owner.id)]


@pytest.fixture
async def pg_mirror_company_admin(
    base_developer_company_admin: Developer,
    pg_mirror_company: PgCompany,
) -> PgDeveloper:
    """Return the Tortoise Developer created by the bridge."""
    return _BEANIE_TO_PG_DEVELOPER[str(base_developer_company_admin.id)]


@pytest.fixture
async def pg_mirror_company_user(
    base_developer_company_user: Developer,
    pg_mirror_company: PgCompany,
) -> PgDeveloper:
    """Return the Tortoise Developer created by the bridge."""
    return _BEANIE_TO_PG_DEVELOPER[str(base_developer_company_user.id)]


async def _create_pg_mirror_user(
    beanie_user: Any,
    pg_company: PgCompany,
    role: str = "PLAYER",
) -> PgUser:
    """Create a Tortoise User mirroring a Beanie User."""
    user = await PgUser.create(
        username=beanie_user.username,
        email=beanie_user.email,
        role=role,
        company=pg_company,
        name_first=getattr(beanie_user, "name_first", None),
        name_last=getattr(beanie_user, "name_last", None),
    )
    user = await PgUser.filter(id=user.id).prefetch_related("campaign_experiences").first()
    _BEANIE_USER_TO_PG_USER[str(beanie_user.id)] = user
    return user


@pytest.fixture
async def pg_mirror_user(base_user: Any, pg_mirror_company: PgCompany) -> PgUser:
    """Create a Tortoise User mirroring the Beanie base_user."""
    return await _create_pg_mirror_user(base_user, pg_mirror_company, role="PLAYER")


@pytest.fixture
async def pg_mirror_user_storyteller(
    base_user_storyteller: Any, pg_mirror_company: PgCompany
) -> PgUser:
    """Create a Tortoise User mirroring the Beanie base_user_storyteller."""
    return await _create_pg_mirror_user(
        base_user_storyteller, pg_mirror_company, role="STORYTELLER"
    )


@pytest.fixture
async def pg_mirror_user_admin(base_user_admin: Any, pg_mirror_company: PgCompany) -> PgUser:
    """Create a Tortoise User mirroring the Beanie base_user_admin."""
    return await _create_pg_mirror_user(base_user_admin, pg_mirror_company, role="ADMIN")


@pytest.fixture
async def pg_mirror_campaign(base_campaign: Any, pg_mirror_company: PgCompany) -> PgCampaign:
    """Create a Tortoise Campaign mirroring the Beanie base_campaign."""
    return await PgCampaign.create(
        name=base_campaign.name,
        company=pg_mirror_company,
    )


@pytest.fixture
async def pg_mirror_campaign_book(
    pg_mirror_campaign: PgCampaign,
) -> PgCampaignBook:
    """Create a Tortoise CampaignBook mirroring a Beanie campaign book."""
    return await PgCampaignBook.create(
        name="Mirror Book",
        number=1,
        campaign=pg_mirror_campaign,
    )


@pytest.fixture
async def pg_mirror_campaign_chapter(
    pg_mirror_campaign_book: PgCampaignBook,
) -> PgCampaignChapter:
    """Create a Tortoise CampaignChapter mirroring a Beanie campaign chapter."""
    return await PgCampaignChapter.create(
        name="Mirror Chapter",
        number=1,
        book=pg_mirror_campaign_book,
    )


@pytest.fixture
async def _patch_pg_bridge(
    base_company: Company,
    base_developer_global_admin: Developer,
    base_developer_company_owner: Developer,
    base_developer_company_admin: Developer,
    base_developer_company_user: Developer,
) -> None:
    """Create Tortoise developers mirroring Beanie auth developers.

    Copy API key credentials so the Tortoise auth middleware finds them.
    Guards and dependency providers work natively — no monkeypatching needed.
    """
    pg_company = await PgCompany.create(
        name=base_company.name,
        email=getattr(base_company, "email", "test@example.com"),
    )
    await PgCompanySettings.create(company=pg_company)
    _BEANIE_COMPANY_TO_PG_COMPANY[str(base_company.id)] = pg_company

    developers_config = [
        (base_developer_global_admin, CompanyPermission.OWNER, True),
        (base_developer_company_owner, CompanyPermission.OWNER, False),
        (base_developer_company_admin, CompanyPermission.ADMIN, False),
        (base_developer_company_user, CompanyPermission.USER, False),
    ]
    for beanie_dev, permission, is_admin in developers_config:
        pg_dev = await PgDeveloper.create(
            username=beanie_dev.username,
            email=beanie_dev.email,
            is_global_admin=is_admin,
            api_key_fingerprint=beanie_dev.api_key_fingerprint,
            hashed_api_key=beanie_dev.hashed_api_key,
            key_generated=getattr(beanie_dev, "key_generated", None),
        )
        await DeveloperCompanyPermission.create(
            developer=pg_dev,
            company=pg_company,
            permission=permission,
        )
        pg_dev = (
            await PgDeveloper.filter(id=pg_dev.id).prefetch_related("permissions__company").first()
        )
        _BEANIE_TO_PG_DEVELOPER[str(beanie_dev.id)] = pg_dev
