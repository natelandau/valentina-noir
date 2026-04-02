"""Shared fixtures for domain integration tests that use Tortoise-based controllers.

The auth middleware resolves a Beanie Developer (MongoDB) from the API key, setting
request.user to a Beanie object whose ID is a PydanticObjectId (12-byte ObjectId).
Controllers migrated to Tortoise query PgDeveloper (PostgreSQL UUID PK) via
provide_developer_from_request. Since ObjectId and UUID are incompatible types,
we bridge the gap by:

1. Creating Tortoise mirror objects (Company, Developer, CompanySettings, Permission)
2. Maintaining a mapping from Beanie developer ID -> Tortoise developer
3. Patching the Provide.dependency on controller classes to use a bridged lookup
4. Patching _pg_check_developer_company_permission to translate Beanie IDs
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

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
from vapi.lib.exceptions import NotFoundError, PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    from litestar.connection import ASGIConnection

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
    """Create a Tortoise Company mirroring the Beanie base_company."""
    company = await PgCompany.create(
        name=base_company.name,
        email=getattr(base_company, "email", "test@example.com"),
    )
    company = await PgCompany.get(id=str(company.id))
    await PgCompanySettings.create(company=company)
    _BEANIE_COMPANY_TO_PG_COMPANY[str(base_company.id)] = company
    return company


async def _create_pg_mirror_developer(
    beanie_developer: Developer,
    pg_company: PgCompany,
    permission: CompanyPermission,
    *,
    is_global_admin: bool = False,
) -> PgDeveloper:
    """Create a Tortoise Developer mirroring a Beanie Developer and link to a company."""
    developer = await PgDeveloper.create(
        username=beanie_developer.username,
        email=beanie_developer.email,
        is_global_admin=is_global_admin,
    )
    await DeveloperCompanyPermission.create(
        developer=developer,
        company=pg_company,
        permission=permission,
    )
    # Re-fetch with permissions prefetched
    developer = (
        await PgDeveloper.filter(id=developer.id).prefetch_related("permissions__company").first()
    )
    _BEANIE_TO_PG_DEVELOPER[str(beanie_developer.id)] = developer
    return developer


@pytest.fixture
async def pg_mirror_global_admin(
    base_developer_global_admin: Developer,
    pg_mirror_company: PgCompany,
) -> PgDeveloper:
    """Create a Tortoise Developer mirroring the Beanie global admin."""
    return await _create_pg_mirror_developer(
        base_developer_global_admin,
        pg_mirror_company,
        CompanyPermission.OWNER,
        is_global_admin=True,
    )


@pytest.fixture
async def pg_mirror_company_owner(
    base_developer_company_owner: Developer,
    pg_mirror_company: PgCompany,
) -> PgDeveloper:
    """Create a Tortoise Developer mirroring the Beanie company owner."""
    return await _create_pg_mirror_developer(
        base_developer_company_owner,
        pg_mirror_company,
        CompanyPermission.OWNER,
    )


@pytest.fixture
async def pg_mirror_company_admin(
    base_developer_company_admin: Developer,
    pg_mirror_company: PgCompany,
) -> PgDeveloper:
    """Create a Tortoise Developer mirroring the Beanie company admin."""
    return await _create_pg_mirror_developer(
        base_developer_company_admin,
        pg_mirror_company,
        CompanyPermission.ADMIN,
    )


@pytest.fixture
async def pg_mirror_company_user(
    base_developer_company_user: Developer,
    pg_mirror_company: PgCompany,
) -> PgDeveloper:
    """Create a Tortoise Developer mirroring the Beanie company user."""
    return await _create_pg_mirror_developer(
        base_developer_company_user,
        pg_mirror_company,
        CompanyPermission.USER,
    )


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


async def _bridged_provide_developer_from_request(request: Any) -> PgDeveloper:
    """Bridge replacement for provide_developer_from_request using Beanie-to-Tortoise map."""
    beanie_id = str(request.user.id)
    developer = _BEANIE_TO_PG_DEVELOPER.get(beanie_id)
    if not developer:
        raise NotFoundError(detail="Developer not found (bridge mapping missing)")
    return developer


async def _bridged_pg_check_developer_company_permission(
    connection: ASGIConnection,
    *,
    allowed_permissions: set[CompanyPermission] | None = None,
) -> None:
    """Bridge replacement for _pg_check_developer_company_permission."""
    beanie_developer = connection.user
    if beanie_developer.is_global_admin:
        return

    company_id_str = connection.path_params.get("company_id")
    if not company_id_str:
        raise ValidationError(
            detail="Company ID is required",
            invalid_parameters=[{"field": "company_id", "message": "Company ID is required"}],
        )

    company = await PgCompany.filter(id=UUID(company_id_str), is_archived=False).first()
    if not company:
        raise NotFoundError(detail=f"Company '{company_id_str}' not found")

    # Look up the Tortoise developer via bridge mapping
    pg_developer = _BEANIE_TO_PG_DEVELOPER.get(str(beanie_developer.id))
    if not pg_developer:
        raise PermissionDeniedError(detail="No rights to access this resource")

    perm = await DeveloperCompanyPermission.filter(
        developer_id=pg_developer.id,
        company_id=UUID(company_id_str),
    ).first()

    if perm and (allowed_permissions is None or perm.permission in allowed_permissions):
        return

    raise PermissionDeniedError(detail="No rights to access this resource")


@pytest.fixture
def _patch_pg_bridge(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch the Tortoise guard helper and controller Provide dependencies.

    The guard helper is called at request time via module-level name lookup,
    so monkeypatching the module attribute works. The Provide.dependency on
    controller classes stores a direct function reference captured at class
    definition time, so we replace it directly on the Provide instance.

    These patches are safe for non-migrated tests because they only affect
    Tortoise-specific code paths that non-migrated controllers don't use.
    """
    from vapi.domain.controllers.campaign.book_controller import CampaignBookController
    from vapi.domain.controllers.campaign.campaign_controller import CampaignController
    from vapi.domain.controllers.campaign.chapter_controller import CampaignChapterController
    from vapi.domain.controllers.character.controllers import CharacterController
    from vapi.domain.controllers.character_generation.controllers import (
        CharacterGenerationController,
    )
    from vapi.domain.controllers.character_inventory.controllers import CharacterInventoryController
    from vapi.domain.controllers.character_trait.controllers import CharacterTraitController
    from vapi.domain.controllers.company.controllers import CompanyController
    from vapi.domain.controllers.developer.controllers import DeveloperController
    from vapi.domain.controllers.dicerolls.controllers import DiceRollController
    from vapi.domain.controllers.notes.book_notes import CampaignBookNoteController
    from vapi.domain.controllers.notes.campaign_notes import CampaignNoteController
    from vapi.domain.controllers.notes.chapter_notes import CampaignChapterNoteController
    from vapi.domain.controllers.notes.character_notes import CharacterNoteController
    from vapi.domain.controllers.notes.user_notes import UserNoteController
    from vapi.domain.controllers.s3_assets.book_assets import BookAssetsController
    from vapi.domain.controllers.s3_assets.campaign_assets import CampaignAssetsController
    from vapi.domain.controllers.s3_assets.chapter_assets import ChapterAssetsController
    from vapi.domain.controllers.s3_assets.character_assets import CharacterAssetsController
    from vapi.domain.controllers.s3_assets.user_assets import UserAssetsController
    from vapi.domain.controllers.statistics.controllers import StatisticsController
    from vapi.domain.controllers.user.experience_controller import ExperienceController
    from vapi.domain.controllers.user.user_controller import UserController

    # Patch the guard helper (called at request time via module name lookup)
    monkeypatch.setattr(
        "vapi.lib.pg_guards._pg_check_developer_company_permission",
        _bridged_pg_check_developer_company_permission,
    )

    # Patch the Provide.dependency on controller classes so Litestar calls
    # our bridged function instead of the original
    for controller_cls in (
        CompanyController,
        DeveloperController,
        UserController,
        ExperienceController,
        CampaignController,
        CampaignBookController,
        CampaignChapterController,
        CharacterController,
        CharacterInventoryController,
        CharacterTraitController,
        CharacterGenerationController,
        CampaignBookNoteController,
        CampaignNoteController,
        CampaignChapterNoteController,
        CharacterNoteController,
        UserNoteController,
        DiceRollController,
        StatisticsController,
        BookAssetsController,
        CampaignAssetsController,
        ChapterAssetsController,
        CharacterAssetsController,
        UserAssetsController,
    ):
        for provide in controller_cls.dependencies.values():
            if (
                hasattr(provide, "dependency")
                and getattr(provide.dependency, "__name__", "") == "provide_developer_from_request"
            ):
                monkeypatch.setattr(provide, "dependency", _bridged_provide_developer_from_request)


@pytest.fixture
def neutralize_after_response_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize the after_response hook for tests using migrated controllers.

    The hook calls Beanie Company.get() with a Tortoise UUID, which fails during
    the mid-migration state. Tests for migrated controllers should request this
    fixture to prevent after_response errors. NOT autouse because non-migrated
    controller tests need the real hooks.
    """
    import vapi.domain.hooks.after_response as _hooks_mod

    async def _noop_async(*_args: Any, **_kwargs: Any) -> None:
        pass

    monkeypatch.setattr(_hooks_mod, "add_audit_log", _noop_async)
    monkeypatch.setattr(_hooks_mod, "delete_response_cache_for_api_key", _noop_async)

    # Replace the Beanie Company.get in the hooks module with one that returns None,
    # preventing the hook from querying MongoDB with a Tortoise UUID
    class _StubCompany:
        @staticmethod
        async def get(*_args: Any, **_kwargs: Any) -> None:
            return None

    monkeypatch.setattr(_hooks_mod, "Company", _StubCompany)
