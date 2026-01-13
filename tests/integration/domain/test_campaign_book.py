"""Test campaign book."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_403_FORBIDDEN,
)

from vapi.constants import UserRole
from vapi.db.models import Campaign, CampaignBook
from vapi.domain.urls import Campaigns

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.models import User

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    "user_role",
    [
        (UserRole.ADMIN),
        (UserRole.STORYTELLER),
        (UserRole.PLAYER),
    ],
)
async def test_book_controller(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    base_user_storyteller: User,
    base_user_admin: User,
    base_user_player: User,
    build_url: Callable[[str, Any], str],
    base_campaign: Campaign,
    base_campaign_book: CampaignBook,
    user_role: UserRole,
    debug: Callable[[Any], None],
) -> None:
    """Verify the campaign controller."""
    if user_role == UserRole.STORYTELLER:
        user = base_user_storyteller
    elif user_role == UserRole.ADMIN:
        user = base_user_admin
    elif user_role == UserRole.PLAYER:
        user = base_user_player

    assert user is not None

    # when we create a book
    response = await client.post(
        build_url(Campaigns.BOOK_CREATE, user_id=user.id),
        headers=token_company_admin,
        json={"name": "Test Book", "description": "Test Description"},
    )

    # then we should get a 201 created response or a 403 forbidden response
    if user_role == UserRole.PLAYER:
        assert response.status_code == HTTP_403_FORBIDDEN
    else:
        assert response.status_code == HTTP_201_CREATED
        # debug(response.json())
        response_json = response.json()
        assert response_json["name"] == "Test Book"
        assert response_json["description"] == "Test Description"
        assert response_json["number"] == 2
        assert response_json["campaign_id"] == str(base_campaign.id)
        assert response_json["date_created"] is not None
        assert response_json["date_modified"] is not None

    # get the new campaign id
    new_campaign_book_id = (
        response_json["id"] if user_role != UserRole.PLAYER else base_campaign_book.id
    )

    # when we update the book
    response = await client.patch(
        build_url(Campaigns.BOOK_UPDATE, book_id=new_campaign_book_id, user_id=user.id),
        headers=token_company_admin,
        json={"name": "Test Book Updated"},
    )

    # then we should get a 200 ok response or a 403 forbidden response
    if user_role == UserRole.PLAYER:
        assert response.status_code == HTTP_403_FORBIDDEN
    else:
        assert response.status_code == HTTP_200_OK
        response_json = response.json()
        assert response_json["name"] == "Test Book Updated"
        assert response_json["description"] == "Test Description"
        assert response_json["number"] == 2
        assert response_json["campaign_id"] == str(base_campaign.id)
        assert response_json["date_modified"] is not None

    # when we delete the book
    response = await client.delete(
        build_url(Campaigns.BOOK_DELETE, book_id=new_campaign_book_id, user_id=user.id),
        headers=token_company_admin,
    )

    # then we should get a 204 no content response or a 403 forbidden response
    if user_role == UserRole.PLAYER:
        assert response.status_code == HTTP_403_FORBIDDEN
    else:
        # debug(response.json())
        assert response.status_code == HTTP_204_NO_CONTENT

    # when we list the books
    response = await client.get(
        build_url(Campaigns.BOOKS, user_id=user.id), headers=token_company_admin
    )
    # debug(response.json())
    assert response.status_code == HTTP_200_OK
    await base_campaign_book.sync()

    # then we should get a 200 ok response with the book in the list
    assert response.json()["items"] == [
        base_campaign_book.model_dump(mode="json", exclude={"is_archived", "archive_date"})
    ]

    # when we get the book
    response = await client.get(
        build_url(Campaigns.BOOK_DETAIL, book_id=base_campaign_book.id, user_id=user.id),
        headers=token_company_admin,
    )
    assert response.status_code == HTTP_200_OK
    assert response.json() == base_campaign_book.model_dump(
        mode="json", exclude={"is_archived", "archive_date"}
    )


async def test_renumber_book(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    base_user_storyteller: User,
    campaign_book_factory: Callable[[Any], CampaignBook],
    build_url: Callable[[str, Any], str],
) -> None:
    """Verify the renumber_book function."""
    await CampaignBook.delete_all()
    book1 = await campaign_book_factory()
    book2 = await campaign_book_factory()
    book3 = await campaign_book_factory()
    book4 = await campaign_book_factory()

    assert book1.number == 1
    assert book2.number == 2
    assert book3.number == 3
    assert book4.number == 4

    response = await client.put(
        build_url(
            Campaigns.BOOK_NUMBER,
            book_id=book1.id,
            user_id=base_user_storyteller.id,
        ),
        json={"number": 3},
        headers=token_company_admin,
    )
    assert response.status_code == HTTP_200_OK
    await book1.sync()
    await book2.sync()
    await book3.sync()
    await book4.sync()

    assert response.json() == book1.model_dump(mode="json", exclude={"is_archived", "archive_date"})
    assert book1.number == 3
    assert book2.number == 1
    assert book3.number == 2
    assert book4.number == 4
