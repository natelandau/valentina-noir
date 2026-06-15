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

from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.character import Character
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.user import User
from vapi.domain.urls import Campaigns

pytestmark = pytest.mark.anyio


async def test_book_controller(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    on_behalf_of_header: dict[str, str],
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
        ),
        headers=token_global_admin | on_behalf_of_header,
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
        ),
        headers=token_global_admin | on_behalf_of_header,
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
        ),
        headers=token_global_admin | on_behalf_of_header,
    )

    # Then we should get a 204 no content response
    assert response.status_code == HTTP_204_NO_CONTENT

    # When we list the books
    response = await client.get(
        build_url(
            Campaigns.BOOKS,
            company_id=session_company.id,
            campaign_id=campaign.id,
        ),
        headers=token_global_admin | on_behalf_of_header,
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
        ),
        headers=token_global_admin | on_behalf_of_header,
    )

    # Then we should get a 200 with the book details
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == str(base_book.id)


async def test_renumber_book(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    on_behalf_of_header: dict[str, str],
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
        ),
        json={"number": 3},
        headers=token_global_admin | on_behalf_of_header,
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
    on_behalf_of_header: dict[str, str],
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
        ),
        headers=token_global_admin | on_behalf_of_header,
    )

    # Then the response has no child keys
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["id"] == str(book.id)
    assert "chapters" not in data
    assert "notes" not in data
    assert "assets" not in data


async def test_get_book_includes_child_counts(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    on_behalf_of_header: dict[str, str],
    session_company: Company,
    session_global_admin,
    session_user: User,
    campaign_factory: Callable[..., Campaign],
    campaign_book_factory: Callable[..., CampaignBook],
    campaign_chapter_factory,
    build_url: Callable[..., str],
) -> None:
    """Verify getBook detail reports exact child resource counts."""
    # Given a book with two chapters and no notes or assets
    campaign = await campaign_factory(company=session_company)
    book = await campaign_book_factory(campaign=campaign)
    await campaign_chapter_factory(book=book)
    await campaign_chapter_factory(book=book)

    # When we get the book detail
    response = await client.get(
        build_url(
            Campaigns.BOOK_DETAIL,
            company_id=session_company.id,
            campaign_id=campaign.id,
            book_id=book.id,
        ),
        headers=token_global_admin | on_behalf_of_header,
    )

    # Then the counts are exact
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert data["num_chapters"] == 2
    assert data["num_notes"] == 0
    assert data["num_assets"] == 0


async def test_get_book_include_all_children(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    on_behalf_of_header: dict[str, str],
    session_company: Company,
    session_global_admin,
    session_user: User,
    campaign_factory: Callable[..., Campaign],
    campaign_book_factory: Callable[..., CampaignBook],
    campaign_chapter_factory,
    character_factory: Callable[..., Character],
    note_factory,
    s3asset_factory,
    build_url: Callable[..., str],
) -> None:
    """Verify getBook with all includes embeds chapters, notes, and assets."""
    # Given a book with one chapter (with a character), one note, and one asset
    campaign = await campaign_factory(company=session_company)
    book = await campaign_book_factory(campaign=campaign)
    chapter = await campaign_chapter_factory(book=book)
    character = await character_factory(company=session_company, campaign=campaign)
    await chapter.characters.add(character)
    note = await note_factory(company=session_company, book=book)
    asset = await s3asset_factory(company=session_company, book=book, uploaded_by=session_user)

    # When we include all child types
    response = await client.get(
        build_url(
            Campaigns.BOOK_DETAIL,
            company_id=session_company.id,
            campaign_id=campaign.id,
            book_id=book.id,
        ),
        headers=token_global_admin | on_behalf_of_header,
        params={"include": ["chapters", "notes", "assets"]},
    )

    # Then all three child lists are present with the created items
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert len(data["chapters"]) == 1
    assert data["chapters"][0]["id"] == str(chapter.id)
    # And the embedded chapter carries its character_ids
    assert data["chapters"][0]["character_ids"] == [str(character.id)]
    assert len(data["notes"]) == 1
    assert data["notes"][0]["id"] == str(note.id)
    assert len(data["assets"]) == 1
    assert data["assets"][0]["id"] == str(asset.id)


async def test_get_book_include_excludes_archived_children(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    on_behalf_of_header: dict[str, str],
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
    """Verify getBook includes drop archived chapters, notes, and assets."""
    # Given a book with one active and one archived of each child type
    campaign = await campaign_factory(company=session_company)
    book = await campaign_book_factory(campaign=campaign)

    active_chapter = await campaign_chapter_factory(book=book)
    archived_chapter = await campaign_chapter_factory(book=book)
    archived_chapter.is_archived = True
    await archived_chapter.save()

    active_note = await note_factory(company=session_company, book=book)
    archived_note = await note_factory(company=session_company, book=book)
    archived_note.is_archived = True
    await archived_note.save()

    active_asset = await s3asset_factory(
        company=session_company, book=book, uploaded_by=session_user
    )
    archived_asset = await s3asset_factory(
        company=session_company, book=book, uploaded_by=session_user
    )
    archived_asset.is_archived = True
    await archived_asset.save()

    # When we include every child type
    response = await client.get(
        build_url(
            Campaigns.BOOK_DETAIL,
            company_id=session_company.id,
            campaign_id=campaign.id,
            book_id=book.id,
        ),
        headers=token_global_admin | on_behalf_of_header,
        params={"include": ["chapters", "notes", "assets"]},
    )

    # Then each list contains only the active child
    assert response.status_code == HTTP_200_OK
    data = response.json()
    assert [c["id"] for c in data["chapters"]] == [str(active_chapter.id)]
    assert [n["id"] for n in data["notes"]] == [str(active_note.id)]
    assert [a["id"] for a in data["assets"]] == [str(active_asset.id)]


async def test_get_book_include_invalid_value(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    on_behalf_of_header: dict[str, str],
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
        ),
        headers=token_global_admin | on_behalf_of_header,
        params={"include": ["bogus"]},
    )

    # Then we get a 400
    assert response.status_code == HTTP_400_BAD_REQUEST


async def test_book_character_rollup(
    client: AsyncClient,
    token_global_admin: dict[str, str],
    on_behalf_of_header: dict[str, str],
    session_company: Company,
    session_global_admin,
    session_user: User,
    campaign_factory: Callable[..., Campaign],
    campaign_book_factory: Callable[..., CampaignBook],
    campaign_chapter_factory: Callable[..., CampaignChapter],
    character_factory: Callable[..., Character],
    build_url: Callable[..., str],
) -> None:
    """Verify a book rolls up the distinct characters across its chapters."""
    # Given a book with two chapters sharing one character and each having a unique one
    campaign = await campaign_factory(company=session_company)
    book = await campaign_book_factory(campaign=campaign)
    chapter_one = await campaign_chapter_factory(book=book)
    chapter_two = await campaign_chapter_factory(book=book)
    shared = await character_factory(company=session_company, campaign=campaign)
    only_one = await character_factory(company=session_company, campaign=campaign)
    only_two = await character_factory(company=session_company, campaign=campaign)
    await chapter_one.characters.add(shared, only_one)
    await chapter_two.characters.add(shared, only_two)

    # When we GET the book
    response = await client.get(
        build_url(
            Campaigns.BOOK_DETAIL,
            company_id=session_company.id,
            campaign_id=campaign.id,
            book_id=book.id,
        ),
        headers=token_global_admin | on_behalf_of_header,
    )

    # Then character_ids is the distinct union across chapters
    assert response.status_code == HTTP_200_OK
    assert sorted(response.json()["character_ids"]) == sorted(
        [str(shared.id), str(only_one.id), str(only_two.id)]
    )

    # When we list books in the campaign
    response = await client.get(
        build_url(Campaigns.BOOKS, company_id=session_company.id, campaign_id=campaign.id),
        headers=token_global_admin | on_behalf_of_header,
    )

    # Then the listed book carries the same rollup
    assert response.status_code == HTTP_200_OK
    listed = next(b for b in response.json()["items"] if b["id"] == str(book.id))
    assert sorted(listed["character_ids"]) == sorted(
        [str(shared.id), str(only_one.id), str(only_two.id)]
    )
