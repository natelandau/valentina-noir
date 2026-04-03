"""Test campaign book."""

from collections.abc import Callable

import pytest
from httpx import AsyncClient
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
)

from vapi.db.sql_models.campaign import Campaign, CampaignBook
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain.urls import Campaigns

pytestmark = pytest.mark.anyio


async def test_book_controller(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    pg_mirror_company: Company,
    pg_mirror_global_admin,
    pg_mirror_user: User,
    pg_campaign_factory: Callable[..., Campaign],
    pg_campaign_book_factory: Callable[..., CampaignBook],
    build_url: Callable[..., str],
) -> None:
    """Verify the campaign book CRUD workflow."""
    # Given a campaign with one book
    campaign = await pg_campaign_factory(company=pg_mirror_company)
    base_book = await pg_campaign_book_factory(campaign=campaign)

    # When we create a book
    response = await client.post(
        build_url(
            Campaigns.BOOK_CREATE,
            company_id=pg_mirror_company.id,
            campaign_id=campaign.id,
            user_id=pg_mirror_user.id,
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
            company_id=pg_mirror_company.id,
            campaign_id=campaign.id,
            book_id=new_book_id,
            user_id=pg_mirror_user.id,
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
            company_id=pg_mirror_company.id,
            campaign_id=campaign.id,
            book_id=new_book_id,
            user_id=pg_mirror_user.id,
        ),
        headers=token_global_admin,
    )

    # Then we should get a 204 no content response
    assert response.status_code == HTTP_204_NO_CONTENT

    # When we list the books
    response = await client.get(
        build_url(
            Campaigns.BOOKS,
            company_id=pg_mirror_company.id,
            campaign_id=campaign.id,
            user_id=pg_mirror_user.id,
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
            company_id=pg_mirror_company.id,
            campaign_id=campaign.id,
            book_id=base_book.id,
            user_id=pg_mirror_user.id,
        ),
        headers=token_global_admin,
    )

    # Then we should get a 200 with the book details
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == str(base_book.id)


async def test_renumber_book(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    pg_mirror_company: Company,
    pg_mirror_global_admin,
    pg_mirror_user: User,
    pg_campaign_factory: Callable[..., Campaign],
    pg_campaign_book_factory: Callable[..., CampaignBook],
    build_url: Callable[..., str],
) -> None:
    """Verify the renumber book endpoint."""
    # Given a campaign with 4 books
    campaign = await pg_campaign_factory(company=pg_mirror_company)
    book1 = await pg_campaign_book_factory(campaign=campaign)
    book2 = await pg_campaign_book_factory(campaign=campaign)
    book3 = await pg_campaign_book_factory(campaign=campaign)
    book4 = await pg_campaign_book_factory(campaign=campaign)

    assert book1.number == 1
    assert book2.number == 2
    assert book3.number == 3
    assert book4.number == 4

    # When book1 is moved to position 3
    response = await client.put(
        build_url(
            Campaigns.BOOK_NUMBER,
            company_id=pg_mirror_company.id,
            campaign_id=campaign.id,
            book_id=book1.id,
            user_id=pg_mirror_user.id,
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
