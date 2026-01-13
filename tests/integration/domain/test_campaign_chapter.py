"""Test campaign chapter."""

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
from vapi.db.models import CampaignBook, CampaignChapter
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
async def test_chapter_controller(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    base_user_storyteller: User,
    base_user_admin: User,
    base_user_player: User,
    build_url: Callable[[str, Any], str],
    base_campaign_book: CampaignBook,
    base_campaign_chapter: CampaignChapter,
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

    # when we create a chapter
    response = await client.post(
        build_url(Campaigns.CHAPTER_CREATE, book_id=base_campaign_book.id, user_id=user.id),
        headers=token_company_admin,
        json={"name": "Test Chapter", "description": "Test Description"},
    )

    # then we should get a 201 created response
    if user_role == UserRole.PLAYER:
        assert response.status_code == HTTP_403_FORBIDDEN
    else:
        assert response.status_code == HTTP_201_CREATED
        # debug(response.json())
        response_json = response.json()
        assert response_json["name"] == "Test Chapter"
        assert response_json["description"] == "Test Description"
        assert response_json["number"] == 2
        assert response_json["book_id"] == str(base_campaign_book.id)
        assert response_json["date_created"] is not None
        assert response_json["date_modified"] is not None

    # given the new campaign chapter id
    new_campaign_chapter_id = (
        response_json["id"] if user_role != UserRole.PLAYER else base_campaign_chapter.id
    )

    # when we update the chapter
    response = await client.patch(
        build_url(Campaigns.CHAPTER_UPDATE, chapter_id=new_campaign_chapter_id, user_id=user.id),
        headers=token_company_admin,
        json={"name": "Test Chapter Updated"},
    )
    if user_role == UserRole.PLAYER:
        assert response.status_code == HTTP_403_FORBIDDEN
    else:
        assert response.status_code == HTTP_200_OK
        response_json = response.json()
        assert response_json["name"] == "Test Chapter Updated"
        assert response_json["description"] == "Test Description"
        assert response_json["number"] == 2
        assert response_json["book_id"] == str(base_campaign_book.id)

    # when we delete the chapter
    response = await client.delete(
        build_url(Campaigns.CHAPTER_DELETE, chapter_id=new_campaign_chapter_id, user_id=user.id),
        headers=token_company_admin,
    )
    if user_role == UserRole.PLAYER:
        assert response.status_code == HTTP_403_FORBIDDEN
    else:
        assert response.status_code == HTTP_204_NO_CONTENT

    # when we list the chapters
    response = await client.get(
        build_url(Campaigns.CHAPTERS, book_id=base_campaign_book.id, user_id=user.id),
        headers=token_company_admin,
    )
    # debug(response.json())
    assert response.status_code == HTTP_200_OK
    await base_campaign_chapter.sync()

    # then we should get a 200 ok response with the chapter in the list
    assert response.json()["items"] == [
        base_campaign_chapter.model_dump(mode="json", exclude={"is_archived", "archive_date"})
    ]

    # when we get the chapter
    response = await client.get(
        build_url(Campaigns.CHAPTER_DETAIL, chapter_id=base_campaign_chapter.id, user_id=user.id),
        headers=token_company_admin,
    )
    # then we should get a 200 ok response with the chapter
    assert response.status_code == HTTP_200_OK
    assert response.json() == base_campaign_chapter.model_dump(
        mode="json", exclude={"is_archived", "archive_date"}
    )


async def test_renumber_chapter(
    client: AsyncClient,
    token_company_admin: dict[str, str],
    base_user_storyteller: User,
    campaign_chapter_factory: Callable[[Any], CampaignChapter],
    build_url: Callable[[str, Any], str],
) -> None:
    """Verify the renumber_chapter function."""
    await CampaignChapter.delete_all()
    chapter1 = await campaign_chapter_factory()
    chapter2 = await campaign_chapter_factory()
    chapter3 = await campaign_chapter_factory()
    chapter4 = await campaign_chapter_factory()

    assert chapter1.number == 1
    assert chapter2.number == 2
    assert chapter3.number == 3
    assert chapter4.number == 4

    response = await client.put(
        build_url(
            Campaigns.CHAPTER_NUMBER,
            chapter_id=chapter1.id,
            user_id=base_user_storyteller.id,
        ),
        json={"number": 3},
        headers=token_company_admin,
    )
    assert response.status_code == HTTP_200_OK
    await chapter1.sync()
    await chapter2.sync()
    await chapter3.sync()
    await chapter4.sync()
    assert response.json() == chapter1.model_dump(
        mode="json", exclude={"is_archived", "archive_date"}
    )
    assert chapter1.number == 3
    assert chapter2.number == 1
    assert chapter3.number == 2
    assert chapter4.number == 4
