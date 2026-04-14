"""Test notes controllers (Tortoise ORM)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_404_NOT_FOUND,
)

from vapi.domain.urls import Campaigns, Characters, Users

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.developer import Developer
    from vapi.db.sql_models.user import User

pytestmark = pytest.mark.anyio


class TestCharacterNotes:
    """Full CRUD tests for character notes (representative tests for all note controllers)."""

    async def test_list_notes_no_results(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable,
    ) -> None:
        """Verify listing notes returns empty when no notes exist."""
        # Given a character with no notes
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )

        response = await client.get(
            build_url(
                Characters.NOTES,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == []

    async def test_list_notes_with_results(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable,
        note_factory: Callable,
    ) -> None:
        """Verify listing notes returns only non-archived notes."""
        # Given a character with notes
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        await note_factory(
            title="Note 1", content="Content 1", character=character, company=session_company
        )
        await note_factory(
            title="Note 2", content="Content 2", character=character, company=session_company
        )
        await note_factory(
            title="Archived Note",
            content="Content",
            character=character,
            company=session_company,
            is_archived=True,
        )

        response = await client.get(
            build_url(
                Characters.NOTES,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        assert response.status_code == HTTP_200_OK
        items = response.json()["items"]
        assert len(items) == 2

    async def test_get_note(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable,
        note_factory: Callable,
    ) -> None:
        """Verify getting a single note by ID."""
        # Given a character with a note
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        note = await note_factory(
            title="Note 1", content="Content 1", character=character, company=session_company
        )

        response = await client.get(
            build_url(
                Characters.NOTE_DETAIL,
                company_id=session_company.id,
                character_id=character.id,
                note_id=note.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        assert response.status_code == HTTP_200_OK
        assert response.json()["id"] == str(note.id)
        assert response.json()["title"] == "Note 1"

    async def test_get_note_not_found(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable,
    ) -> None:
        """Verify 404 when getting a note that doesn't exist."""
        # Given a character
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )

        response = await client.get(
            build_url(
                Characters.NOTE_DETAIL,
                company_id=session_company.id,
                character_id=character.id,
                note_id=uuid4(),
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Note not found"

    async def test_create_note(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable,
    ) -> None:
        """Verify creating a new note."""
        # Given a character
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )

        response = await client.post(
            build_url(
                Characters.NOTE_CREATE,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={"title": "New Note", "content": "New Content"},
        )

        assert response.status_code == HTTP_201_CREATED
        data = response.json()
        assert data["title"] == "New Note"
        assert data["content"] == "New Content"
        assert data["character_id"] == str(character.id)
        assert data["company_id"] == str(session_company.id)

    async def test_update_note(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable,
        note_factory: Callable,
    ) -> None:
        """Verify updating an existing note."""
        # Given a character with a note
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        note = await note_factory(
            title="Original Title",
            content="Original Content",
            character=character,
            company=session_company,
        )

        response = await client.patch(
            build_url(
                Characters.NOTE_UPDATE,
                company_id=session_company.id,
                character_id=character.id,
                note_id=note.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={"title": "Updated Title", "content": "Updated Content"},
        )

        assert response.status_code == HTTP_200_OK
        assert response.json()["title"] == "Updated Title"
        assert response.json()["content"] == "Updated Content"

    async def test_delete_note(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable,
        note_factory: Callable,
    ) -> None:
        """Verify soft-deleting a note."""
        # Given a character with a note
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )
        note = await note_factory(
            title="Note to Delete",
            content="Content",
            character=character,
            company=session_company,
        )

        response = await client.delete(
            build_url(
                Characters.NOTE_DELETE,
                company_id=session_company.id,
                character_id=character.id,
                note_id=note.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        assert response.status_code == HTTP_204_NO_CONTENT
        await note.refresh_from_db()
        assert note.is_archived is True


class TestAllNoteControllersSmoke:
    """Parametrized smoke tests to verify all note controller routes are working."""

    async def test_character_notes_smoke(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        character_factory: Callable,
    ) -> None:
        """Verify character notes create and list operations work."""
        character = await character_factory(
            company=session_company,
            user_player=session_user,
            user_creator=session_user,
            campaign=session_campaign,
        )

        # When we create a note
        create_response = await client.post(
            build_url(
                Characters.NOTE_CREATE,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={"title": "Smoke Test Note", "content": "Smoke test content"},
        )

        # Then it should be created successfully
        assert create_response.status_code == HTTP_201_CREATED
        note_id = create_response.json()["id"]

        # When we list notes
        list_response = await client.get(
            build_url(
                Characters.NOTES,
                company_id=session_company.id,
                character_id=character.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then the created note should appear in the list
        assert list_response.status_code == HTTP_200_OK
        note_ids = [item["id"] for item in list_response.json()["items"]]
        assert note_id in note_ids

    async def test_campaign_notes_smoke(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
    ) -> None:
        """Verify campaign notes create and list operations work."""
        # When we create a note
        create_response = await client.post(
            build_url(
                Campaigns.NOTE_CREATE,
                company_id=session_company.id,
                campaign_id=session_campaign.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={"title": "Campaign Smoke Note", "content": "Campaign smoke content"},
        )

        # Then it should be created successfully
        assert create_response.status_code == HTTP_201_CREATED
        note_id = create_response.json()["id"]

        # When we list notes
        list_response = await client.get(
            build_url(
                Campaigns.NOTES,
                company_id=session_company.id,
                campaign_id=session_campaign.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then the created note should appear in the list
        assert list_response.status_code == HTTP_200_OK
        note_ids = [item["id"] for item in list_response.json()["items"]]
        assert note_id in note_ids

    async def test_user_notes_smoke(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
    ) -> None:
        """Verify user notes create and list operations work."""
        # When we create a note
        create_response = await client.post(
            build_url(
                Users.NOTE_CREATE,
                company_id=session_company.id,
                user_id=session_user.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={"title": "User Smoke Note", "content": "User smoke content"},
        )

        # Then it should be created successfully
        assert create_response.status_code == HTTP_201_CREATED
        note_id = create_response.json()["id"]

        # When we list notes
        list_response = await client.get(
            build_url(
                Users.LIST_NOTES,
                company_id=session_company.id,
                user_id=session_user.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then the created note should appear in the list
        assert list_response.status_code == HTTP_200_OK
        note_ids = [item["id"] for item in list_response.json()["items"]]
        assert note_id in note_ids

    async def test_book_notes_smoke(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        session_campaign_book: CampaignBook,
    ) -> None:
        """Verify campaign book notes create and list operations work."""
        # When we create a note
        create_response = await client.post(
            build_url(
                Campaigns.BOOK_NOTE_CREATE,
                company_id=session_company.id,
                campaign_id=session_campaign.id,
                book_id=session_campaign_book.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={"title": "Book Smoke Note", "content": "Book smoke content"},
        )

        # Then it should be created successfully
        assert create_response.status_code == HTTP_201_CREATED
        note_id = create_response.json()["id"]

        # When we list notes
        list_response = await client.get(
            build_url(
                Campaigns.BOOK_NOTES,
                company_id=session_company.id,
                campaign_id=session_campaign.id,
                book_id=session_campaign_book.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then the created note should appear in the list
        assert list_response.status_code == HTTP_200_OK
        note_ids = [item["id"] for item in list_response.json()["items"]]
        assert note_id in note_ids

    async def test_chapter_notes_smoke(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_global_admin: dict[str, str],
        on_behalf_of_header: dict[str, str],
        session_company: Company,
        session_global_admin: Developer,
        session_user: User,
        session_campaign: Campaign,
        session_campaign_book: CampaignBook,
        session_campaign_chapter: CampaignChapter,
    ) -> None:
        """Verify campaign chapter notes create and list operations work."""
        # When we create a note
        create_response = await client.post(
            build_url(
                Campaigns.CHAPTER_NOTE_CREATE,
                company_id=session_company.id,
                campaign_id=session_campaign.id,
                book_id=session_campaign_book.id,
                chapter_id=session_campaign_chapter.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
            json={"title": "Chapter Smoke Note", "content": "Chapter smoke content"},
        )

        # Then it should be created successfully
        assert create_response.status_code == HTTP_201_CREATED
        note_id = create_response.json()["id"]

        # When we list notes
        list_response = await client.get(
            build_url(
                Campaigns.CHAPTER_NOTES,
                company_id=session_company.id,
                campaign_id=session_campaign.id,
                book_id=session_campaign_book.id,
                chapter_id=session_campaign_chapter.id,
            ),
            headers=token_global_admin | on_behalf_of_header,
        )

        # Then the created note should appear in the list
        assert list_response.status_code == HTTP_200_OK
        note_ids = [item["id"] for item in list_response.json()["items"]]
        assert note_id in note_ids
