"""Authentication middleware tests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from vapi.cli.lib.factories import DeveloperFactory
from vapi.constants import AUTH_HEADER_KEY, IGNORE_RATE_LIMIT_HEADER_KEY
from vapi.domain import urls as vapi_urls

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.models import Company

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
        # vapi_urls.Developers.ME,
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
        vapi_urls.CharacterBlueprints.CATEGORY_TRAITS,
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
        # vapi_urls.Developers.NEW_KEY,
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
        vapi_urls.Characters.TRAIT_INCREASE,
        vapi_urls.Characters.TRAIT_DECREASE,
    ],
    "PATCH": [
        vapi_urls.Dictionaries.UPDATE,
        vapi_urls.Characters.UPDATE,
        vapi_urls.Characters.NOTE_UPDATE,
        vapi_urls.Companies.UPDATE,
        vapi_urls.GlobalAdmin.DEVELOPER_UPDATE,
        # vapi_urls.Developers.UPDATE,
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


@pytest.mark.no_clean_db
async def test_no_auth(
    client: AsyncClient,
    debug: Callable[[Any], None],
) -> None:
    """Test no auth."""
    for method, urls in test_data.items():
        for url in urls:
            base_url = url.replace(":str", "").format(
                company_id="123",
                user_id="123",
                campaign_id="123",
                character_id="123",
                book_id="123",
                chapter_id="123",
                game_version="V4",
                section_id="123",
                character_trait_id="123",
                diceroll_id="123",
                category_id="123",
                trait_id="123",
                note_id="123",
                dictionary_term_id="123",
                developer_id="123",
            )
            # debug(base_url)

            response = await client.request(
                method, base_url, headers={IGNORE_RATE_LIMIT_HEADER_KEY: "true"}
            )
            assert response.status_code == HTTP_401_UNAUTHORIZED


@pytest.mark.no_clean_db
async def test_no_company_permission(
    client: AsyncClient,
    base_company: Company,
    debug: Callable[[Any], None],
) -> None:
    """Test no company permission."""
    developer = DeveloperFactory().build(is_archived=False, is_global_admin=False)
    await developer.save()
    api_key = await developer.generate_api_key()

    for method, urls in test_data.items():
        for url in urls:
            if url in [vapi_urls.Companies.LIST, vapi_urls.System.HEALTH]:
                continue
            base_url = url.replace(":str", "").format(
                company_id=base_company.id,
                user_id="123",
                campaign_id="123",
                character_id="123",
                book_id="123",
                chapter_id="123",
                game_version="V4",
                section_id="123",
                character_trait_id="123",
                diceroll_id="123",
                category_id="123",
                trait_id="123",
                note_id="123",
                dictionary_term_id="123",
                developer_id="123",
            )
            # debug(base_url)

            response = await client.request(
                method,
                base_url,
                headers={AUTH_HEADER_KEY: api_key, IGNORE_RATE_LIMIT_HEADER_KEY: "true"},
            )
            assert response.status_code == HTTP_403_FORBIDDEN
