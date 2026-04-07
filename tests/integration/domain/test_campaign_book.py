"""Test campaign book."""

from collections.abc import Callable

import pytest
from httpx import AsyncClient
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
)

from vapi.db.sql_models.campaign import Campaign, CampaignBook
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain.urls import Campaigns

pytestmark = pytest.mark.anyio


async def test_book_controller(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    session_company: Company,
    session_global_admin,
    session_user: User,
    campaign_factory: Callable[..., Campaign],
    campaign_book_factory: Callable[..., CampaignBook],
    build_url: Callable[..., str],
) -> None:
    """Verify the campaign book CRUD workflow."""
    # Given a campaign with one book
    campaign = await campaign_factory(company=session_company)
    base_book = await campaign_book_factory(campaign=campaign)

    # When we create a book
    response = await client.post(
        build_url(
            Campaigns.BOOK_CREATE,
            company_id=session_company.id,
            campaign_id=campaign.id,
            user_id=session_user.id,
        ),
        headers=token_global_admin,
        json={"name": "Test Book", "description": "Test Description"},
    )

    # Then we should get a 201 created response
    assert response.status_code == HTTP_201_CREATED
    response_json = response.json()
    assert response_json["name"] == "Test Book"
    assert response_json["description"] == "Test Description"
    assert response_json["number"] == 2
    assert response_json["campaign_id"] == str(campaign.id)
    assert response_json["date_created"] is not None
    assert response_json["date_modified"] is not None

    # Given the new book id
    new_book_id = response_json["id"]

    # When we update the book
    response = await client.patch(
        build_url(
            Campaigns.BOOK_UPDATE,
            company_id=session_company.id,
            campaign_id=campaign.id,
            book_id=new_book_id,
            user_id=session_user.id,
        ),
        headers=token_global_admin,
        json={"name": "Test Book Updated"},
    )

    # Then we should get a 200 ok response
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json["name"] == "Test Book Updated"
    assert response_json["description"] == "Test Description"
    assert response_json["number"] == 2

    # When we delete the book
    response = await client.delete(
        build_url(
            Campaigns.BOOK_DELETE,
            company_id=session_company.id,
            campaign_id=campaign.id,
            book_id=new_book_id,
            user_id=session_user.id,
        ),
        headers=token_global_admin,
    )

    # Then we should get a 204 no content response
    assert response.status_code == HTTP_204_NO_CONTENT

    # When we list the books
    response = await client.get(
        build_url(
            Campaigns.BOOKS,
            company_id=session_company.id,
            campaign_id=campaign.id,
            user_id=session_user.id,
        ),
        headers=token_global_admin,
    )

    # Then we should get a 200 with only the base book
    assert response.status_code == HTTP_200_OK
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == str(base_book.id)

    # When we get the book
    response = await client.get(
        build_url(
            Campaigns.BOOK_DETAIL,
            company_id=session_company.id,
            campaign_id=campaign.id,
            book_id=base_book.id,
            user_id=session_user.id,
        ),
        headers=token_global_admin,
    )

    # Then we should get a 200 with the book details
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == str(base_book.id)


async def test_renumber_book(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    session_company: Company,
    session_global_admin,
    session_user: User,
    campaign_factory: Callable[..., Campaign],
    campaign_book_factory: Callable[..., CampaignBook],
    build_url: Callable[..., str],
) -> None:
    """Verify the renumber book endpoint."""
    # Given a campaign with 4 books
    campaign = await campaign_factory(company=session_company)
    book1 = await campaign_book_factory(campaign=campaign)
    book2 = await campaign_book_factory(campaign=campaign)
    book3 = await campaign_book_factory(campaign=campaign)
    book4 = await campaign_book_factory(campaign=campaign)

    assert book1.number == 1
    assert book2.number == 2
    assert book3.number == 3
    assert book4.number == 4

    # When book1 is moved to position 3
    response = await client.put(
        build_url(
            Campaigns.BOOK_NUMBER,
            company_id=session_company.id,
            campaign_id=campaign.id,
            book_id=book1.id,
            user_id=session_user.id,
        ),
        json={"number": 3},
        headers=token_global_admin,
    )

    # Then we should get a 200 with updated positions
    assert response.status_code == HTTP_200_OK
    await book1.refresh_from_db()
    await book2.refresh_from_db()
    await book3.refresh_from_db()
    await book4.refresh_from_db()

    assert response.json()["id"] == str(book1.id)
    assert book1.number == 3
    assert book2.number == 1
    assert book3.number == 2
    assert book4.number == 4


async def test_get_book_no_include_omits_children(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    session_company: Company,
    session_global_admin,
    session_user: User,
    campaign_factory: Callable[..., Campaign],
    campaign_book_factory: Callable[..., CampaignBook],
    build_url: Callable[..., str],
) -> None:
    """Verify getBook without include param omits child resource keys."""
    # Given a book
    campaign = await campaign_factory(company=session_company)
    book = await campaign_book_factory(campaign=campaign)

    # When we get the book without include
    response = await client.get(
        build_url(
            Campaigns.BOOK_DETAIL,
            company_id=session_company.id,
            campaign_id=campaign.id,
            book_id=book.id,
            user_id=session_user.id,
        ),
        headers=token_global_admin,
    )

    # Then the response has no child keys
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["id"] == str(book.id)
    assert "chapters" not in data
    assert "notes" not in data
    assert "assets" not in data


async def test_get_book_include_all_children(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    session_company: Company,
    session_global_admin,
    session_user: User,
    campaign_factory: Callable[..., Campaign],
    campaign_book_factory: Callable[..., CampaignBook],
    campaign_chapter_factory,
    note_factory,
    s3asset_factory,
    build_url: Callable[..., str],
) -> None:
    """Verify getBook with all includes embeds chapters, notes, and assets."""
    # Given a book with one chapter, one note, and one asset
    campaign = await campaign_factory(company=session_company)
    book = await campaign_book_factory(campaign=campaign)
    chapter = await campaign_chapter_factory(book=book)
    note = await note_factory(company=session_company, book=book)
    asset = await s3asset_factory(company=session_company, book=book, uploaded_by=session_user)

    # When we include all child types
    response = await client.get(
        build_url(
            Campaigns.BOOK_DETAIL,
            company_id=session_company.id,
            campaign_id=campaign.id,
            book_id=book.id,
            user_id=session_user.id,
        ),
        headers=token_global_admin,
        params={"include": ["chapters", "notes", "assets"]},
    )

    # Then all three child lists are present with the created items
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert len(data["chapters"]) == 1
    assert data["chapters"][0]["id"] == str(chapter.id)
    assert len(data["notes"]) == 1
    assert data["notes"][0]["id"] == str(note.id)
    assert len(data["assets"]) == 1
    assert data["assets"][0]["id"] == str(asset.id)


async def test_get_book_include_invalid_value(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    session_company: Company,
    session_global_admin,
    session_user: User,
    campaign_factory: Callable[..., Campaign],
    campaign_book_factory: Callable[..., CampaignBook],
    build_url: Callable[..., str],
) -> None:
    """Verify invalid include value returns 400."""
    # Given a book
    campaign = await campaign_factory(company=session_company)
    book = await campaign_book_factory(campaign=campaign)

    # When we pass an invalid include value
    response = await client.get(
        build_url(
            Campaigns.BOOK_DETAIL,
            company_id=session_company.id,
            campaign_id=campaign.id,
            book_id=book.id,
            user_id=session_user.id,
        ),
        headers=token_global_admin,
        params={"include": ["bogus"]},
    )

    # Then we get a 400
    assert response.status_code == HTTP_400_BAD_REQUEST
