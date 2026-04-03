"""Authentication middleware tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from litestar.status_codes import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from vapi.constants import AUTH_HEADER_KEY, IGNORE_RATE_LIMIT_HEADER_KEY
from vapi.db.sql_models.developer import Developer
from vapi.domain import urls as vapi_urls
from vapi.domain.services.developer_svc import DeveloperService

if TYPE_CHECKING:
    from httpx import AsyncClient

    from vapi.db.sql_models.company import Company

pytestmark = pytest.mark.anyio

test_data = {
    "GET": [
        vapi_urls.System.HEALTH,
        vapi_urls.Dictionaries.LIST,
        vapi_urls.Dictionaries.DETAIL,
        vapi_urls.Characters.LIST,
        vapi_urls.Characters.DETAIL,
        vapi_urls.Characters.NOTES,
        vapi_urls.Characters.NOTE_DETAIL,
        vapi_urls.Companies.DETAIL,
        vapi_urls.Companies.LIST,
        vapi_urls.GlobalAdmin.DEVELOPERS,
        vapi_urls.GlobalAdmin.DEVELOPER_DETAIL,
        vapi_urls.Campaigns.LIST,
        vapi_urls.Campaigns.DETAIL,
        vapi_urls.Campaigns.BOOKS,
        vapi_urls.Campaigns.BOOK_DETAIL,
        vapi_urls.Campaigns.CHAPTERS,
        vapi_urls.Campaigns.CHAPTER_DETAIL,
        vapi_urls.CharacterBlueprints.SECTIONS,
        vapi_urls.CharacterBlueprints.SECTION_DETAIL,
        vapi_urls.CharacterBlueprints.CATEGORIES,
        vapi_urls.CharacterBlueprints.CATEGORY_DETAIL,
        vapi_urls.CharacterBlueprints.SUBCATEGORIES,
        vapi_urls.CharacterBlueprints.SUBCATEGORY_DETAIL,
        vapi_urls.CharacterBlueprints.TRAIT_DETAIL,
        vapi_urls.Characters.TRAITS,
        vapi_urls.Characters.TRAIT_DETAIL,
        vapi_urls.DiceRolls.LIST,
        vapi_urls.DiceRolls.DETAIL,
        vapi_urls.Users.LIST,
        vapi_urls.Users.DETAIL,
        vapi_urls.Users.EXPERIENCE_CAMPAIGN,
    ],
    "POST": [
        vapi_urls.Dictionaries.CREATE,
        vapi_urls.Characters.CREATE,
        vapi_urls.Characters.NOTE_CREATE,
        vapi_urls.Companies.CREATE,
        vapi_urls.GlobalAdmin.DEVELOPER_CREATE,
        vapi_urls.Campaigns.CREATE,
        vapi_urls.Campaigns.BOOK_CREATE,
        vapi_urls.Campaigns.CHAPTER_CREATE,
        vapi_urls.Characters.TRAIT_ASSIGN,
        vapi_urls.Characters.TRAIT_CREATE,
        vapi_urls.DiceRolls.CREATE,
        vapi_urls.Users.CREATE,
        vapi_urls.Users.XP_ADD,
        vapi_urls.Users.XP_REMOVE,
        vapi_urls.Users.CP_ADD,
    ],
    "PUT": [
        vapi_urls.Characters.TRAIT_VALUE,
    ],
    "PATCH": [
        vapi_urls.Dictionaries.UPDATE,
        vapi_urls.Characters.UPDATE,
        vapi_urls.Characters.NOTE_UPDATE,
        vapi_urls.Companies.UPDATE,
        vapi_urls.GlobalAdmin.DEVELOPER_UPDATE,
        vapi_urls.Campaigns.UPDATE,
        vapi_urls.Campaigns.BOOK_UPDATE,
        vapi_urls.Campaigns.CHAPTER_UPDATE,
        vapi_urls.Users.UPDATE,
    ],
    "DELETE": [
        vapi_urls.Dictionaries.DELETE,
        vapi_urls.Characters.DELETE,
        vapi_urls.Characters.NOTE_DELETE,
        vapi_urls.Companies.DELETE,
        vapi_urls.GlobalAdmin.DEVELOPER_DELETE,
        vapi_urls.Campaigns.DELETE,
        vapi_urls.Campaigns.BOOK_DELETE,
        vapi_urls.Campaigns.CHAPTER_DELETE,
        vapi_urls.Characters.TRAIT_DELETE,
        vapi_urls.Users.DELETE,
    ],
}

_DUMMY_ID = "123"
_PLACEHOLDER_IDS = {
    "user_id": _DUMMY_ID,
    "campaign_id": _DUMMY_ID,
    "character_id": _DUMMY_ID,
    "book_id": _DUMMY_ID,
    "chapter_id": _DUMMY_ID,
    "game_version": "V4",
    "section_id": _DUMMY_ID,
    "character_trait_id": _DUMMY_ID,
    "diceroll_id": _DUMMY_ID,
    "category_id": _DUMMY_ID,
    "trait_id": _DUMMY_ID,
    "subcategory_id": _DUMMY_ID,
    "note_id": _DUMMY_ID,
    "dictionary_term_id": _DUMMY_ID,
    "developer_id": _DUMMY_ID,
}


def _format_url(url: str, **overrides: str) -> str:
    """Format a URL template with dummy IDs, allowing specific overrides."""
    return url.replace(":str", "").format(
        **{**_PLACEHOLDER_IDS, "company_id": _DUMMY_ID, **overrides}
    )


async def test_no_auth(
    client: AsyncClient,
) -> None:
    """Verify all endpoints reject requests without authentication."""
    for method, urls in test_data.items():
        for url in urls:
            response = await client.request(
                method, _format_url(url), headers={IGNORE_RATE_LIMIT_HEADER_KEY: "true"}
            )
            assert response.status_code == HTTP_401_UNAUTHORIZED


async def test_no_company_permission(
    client: AsyncClient,
    mirror_company: Company,
) -> None:
    """Verify endpoints reject requests from developers without company access."""
    # Create a Tortoise developer with no company permissions
    developer = await Developer.create(
        username="no-perm-dev",
        email="no-perm@example.com",
        is_global_admin=False,
    )
    api_key = await DeveloperService().generate_api_key(developer)

    for method, urls in test_data.items():
        for url in urls:
            if url in {vapi_urls.Companies.LIST, vapi_urls.System.HEALTH}:
                continue

            response = await client.request(
                method,
                _format_url(url, company_id=str(mirror_company.id)),
                headers={AUTH_HEADER_KEY: api_key, IGNORE_RATE_LIMIT_HEADER_KEY: "true"},
            )
            assert response.status_code == HTTP_403_FORBIDDEN
