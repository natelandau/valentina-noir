"""Test campaign chapter."""

from collections.abc import Callable

import pytest
from httpx import AsyncClient
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
)

from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain.urls import Campaigns

pytestmark = pytest.mark.anyio


async def test_chapter_controller(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    pg_mirror_company: Company,
    pg_mirror_global_admin,
    pg_mirror_user: User,
    pg_campaign_factory: Callable[..., Campaign],
    pg_campaign_book_factory: Callable[..., CampaignBook],
    pg_campaign_chapter_factory: Callable[..., CampaignChapter],
    build_url: Callable[..., str],
) -> None:
    """Verify the campaign chapter CRUD workflow."""
    # Given a campaign with a book and one chapter
    campaign = await pg_campaign_factory(company=pg_mirror_company)
    book = await pg_campaign_book_factory(campaign=campaign)
    base_chapter = await pg_campaign_chapter_factory(book=book)

    # When we create a chapter
    response = await client.post(
        build_url(
            Campaigns.CHAPTER_CREATE,
            company_id=pg_mirror_company.id,
            campaign_id=campaign.id,
            book_id=book.id,
            user_id=pg_mirror_user.id,
        ),
        headers=token_global_admin,
        json={"name": "Test Chapter", "description": "Test Description"},
    )

    # Then we should get a 201 created response
    assert response.status_code == HTTP_201_CREATED
    response_json = response.json()
    assert response_json["name"] == "Test Chapter"
    assert response_json["description"] == "Test Description"
    assert response_json["number"] == 2
    assert response_json["book_id"] == str(book.id)
    assert response_json["date_created"] is not None
    assert response_json["date_modified"] is not None

    # Given the new chapter id
    new_chapter_id = response_json["id"]

    # When we update the chapter
    response = await client.patch(
        build_url(
            Campaigns.CHAPTER_UPDATE,
            company_id=pg_mirror_company.id,
            campaign_id=campaign.id,
            book_id=book.id,
            chapter_id=new_chapter_id,
            user_id=pg_mirror_user.id,
        ),
        headers=token_global_admin,
        json={"name": "Test Chapter Updated"},
    )

    # Then we should get a 200 ok response
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["name"] == "Test Chapter Updated"
    assert response_json["description"] == "Test Description"
    assert response_json["number"] == 2

    # When we delete the chapter
    response = await client.delete(
        build_url(
            Campaigns.CHAPTER_DELETE,
            company_id=pg_mirror_company.id,
            campaign_id=campaign.id,
            book_id=book.id,
            chapter_id=new_chapter_id,
            user_id=pg_mirror_user.id,
        ),
        headers=token_global_admin,
    )

    # Then we should get a 204 no content response
    assert response.status_code == HTTP_204_NO_CONTENT

    # When we list the chapters
    response = await client.get(
        build_url(
            Campaigns.CHAPTERS,
            company_id=pg_mirror_company.id,
            campaign_id=campaign.id,
            book_id=book.id,
            user_id=pg_mirror_user.id,
        ),
        headers=token_global_admin,
    )

    # Then we should get a 200 with only the base chapter
    assert response.status_code == HTTP_200_OK
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == str(base_chapter.id)

    # When we get the chapter
    response = await client.get(
        build_url(
            Campaigns.CHAPTER_DETAIL,
            company_id=pg_mirror_company.id,
            campaign_id=campaign.id,
            book_id=book.id,
            chapter_id=base_chapter.id,
            user_id=pg_mirror_user.id,
        ),
        headers=token_global_admin,
    )

    # Then we should get a 200 with the chapter details
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == str(base_chapter.id)


async def test_renumber_chapter(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    pg_mirror_company: Company,
    pg_mirror_global_admin,
    pg_mirror_user: User,
    pg_campaign_factory: Callable[..., Campaign],
    pg_campaign_book_factory: Callable[..., CampaignBook],
    pg_campaign_chapter_factory: Callable[..., CampaignChapter],
    build_url: Callable[..., str],
) -> None:
    """Verify the renumber chapter endpoint."""
    # Given a book with 4 chapters
    campaign = await pg_campaign_factory(company=pg_mirror_company)
    book = await pg_campaign_book_factory(campaign=campaign)
    chapter1 = await pg_campaign_chapter_factory(book=book)
    chapter2 = await pg_campaign_chapter_factory(book=book)
    chapter3 = await pg_campaign_chapter_factory(book=book)
    chapter4 = await pg_campaign_chapter_factory(book=book)

    assert chapter1.number == 1
    assert chapter2.number == 2
    assert chapter3.number == 3
    assert chapter4.number == 4

    # When chapter1 is moved to position 3
    response = await client.put(
        build_url(
            Campaigns.CHAPTER_NUMBER,
            company_id=pg_mirror_company.id,
            campaign_id=campaign.id,
            book_id=book.id,
            chapter_id=chapter1.id,
            user_id=pg_mirror_user.id,
        ),
        json={"number": 3},
        headers=token_global_admin,
    )

    # Then we should get a 200 with updated positions
    assert response.status_code == HTTP_200_OK
    await chapter1.refresh_from_db()
    await chapter2.refresh_from_db()
    await chapter3.refresh_from_db()
    await chapter4.refresh_from_db()

    assert response.json()["id"] == str(chapter1.id)
    assert chapter1.number == 3
    assert chapter2.number == 1
    assert chapter3.number == 2
    assert chapter4.number == 4
