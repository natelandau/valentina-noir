"""Test notes controllers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from beanie import PydanticObjectId
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
)

from vapi.db.models import Note
from vapi.domain.urls import Campaigns, Characters, Users

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.models import Campaign, CampaignBook, CampaignChapter, Character, User

pytestmark = pytest.mark.anyio

NOTE_EXCLUDE_FIELDS = {
    "archive_date",
    "is_archived",
    "company_id",
    "campaign_id",
    "book_id",
    "chapter_id",
    "user_id",
    "character_id",
}


class TestCharacterNotes:
    """Full CRUD tests for character notes (representative tests for all note controllers)."""

    async def test_list_notes_no_results(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_character: Character,
    ) -> None:
        """Verify listing notes returns empty when no notes exist."""
        response = await client.get(
            build_url(Characters.NOTES, character_id=base_character.id),
            headers=token_company_admin,
        )

        assert response.status_code == HTTP_200_OK
        assert response.json()["items"] == []

    async def test_list_notes_with_results(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_character: Character,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify listing notes returns only non-archived notes."""
        note1 = await note_factory(
            title="Note 1", content="Content 1", character_id=base_character.id
        )
        note2 = await note_factory(
            title="Note 2", content="Content 2", character_id=base_character.id
        )
        await note_factory(
            title="Archived Note",
            content="Content",
            character_id=base_character.id,
            is_archived=True,
        )

        response = await client.get(
            build_url(Characters.NOTES, character_id=base_character.id),
            headers=token_company_admin,
        )

        assert response.status_code == HTTP_200_OK
        items = response.json()["items"]
        assert len(items) == 2
        assert items[0] == note1.model_dump(mode="json", exclude=NOTE_EXCLUDE_FIELDS)
        assert items[1] == note2.model_dump(mode="json", exclude=NOTE_EXCLUDE_FIELDS)

    async def test_get_note(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_character: Character,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify getting a single note by ID."""
        note = await note_factory(
            title="Note 1", content="Content 1", character_id=base_character.id
        )

        response = await client.get(
            build_url(Characters.NOTE_DETAIL, note_id=note.id),
            headers=token_company_admin,
        )

        assert response.status_code == HTTP_200_OK
        assert response.json() == note.model_dump(mode="json", exclude=NOTE_EXCLUDE_FIELDS)

    async def test_get_note_not_found(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
    ) -> None:
        """Verify 404 when getting a note that doesn't exist."""
        response = await client.get(
            build_url(Characters.NOTE_DETAIL, note_id=PydanticObjectId()),
            headers=token_company_admin,
        )

        assert response.status_code == HTTP_404_NOT_FOUND
        assert response.json()["detail"] == "Note not found"

    async def test_create_note(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_character: Character,
    ) -> None:
        """Verify creating a new note."""
        response = await client.post(
            build_url(Characters.NOTE_CREATE, character_id=base_character.id),
            headers=token_company_admin,
            json={"title": "New Note", "content": "New Content"},
        )

        assert response.status_code == HTTP_201_CREATED
        note = await Note.get(response.json()["id"])
        assert response.json() == note.model_dump(mode="json", exclude=NOTE_EXCLUDE_FIELDS)
        assert note.character_id == base_character.id

    async def test_create_note_invalid_parameters(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_character: Character,
    ) -> None:
        """Verify 400 when creating a note with invalid parameters."""
        response = await client.post(
            build_url(Characters.NOTE_CREATE, character_id=base_character.id),
            headers=token_company_admin,
            json={"title": "", "content": ""},
        )

        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["invalid_parameters"][0]["field"] == ["title"]
        assert "at least 3 characters" in response.json()["invalid_parameters"][0]["message"]
        assert response.json()["invalid_parameters"][1]["field"] == ["content"]
        assert "at least 3 characters" in response.json()["invalid_parameters"][1]["message"]

    async def test_update_note(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_character: Character,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify updating an existing note."""
        note = await note_factory(
            title="Original Title", content="Original Content", character_id=base_character.id
        )

        response = await client.patch(
            build_url(Characters.NOTE_UPDATE, note_id=note.id),
            headers=token_company_admin,
            json={"title": "Updated Title", "content": "Updated Content"},
        )

        assert response.status_code == HTTP_200_OK
        updated_note = await Note.get(note.id)
        assert response.json() == updated_note.model_dump(mode="json", exclude=NOTE_EXCLUDE_FIELDS)
        assert updated_note.title == "Updated Title"
        assert updated_note.content == "Updated Content"

    async def test_update_note_invalid_parameters(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_character: Character,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify 400 when updating a note with invalid parameters."""
        note = await note_factory(title="Note", content="Content", character_id=base_character.id)

        response = await client.patch(
            build_url(Characters.NOTE_UPDATE, note_id=note.id),
            headers=token_company_admin,
            json={"title": "", "content": ""},
        )

        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["invalid_parameters"][0]["field"] == ["title"]
        assert response.json()["invalid_parameters"][1]["field"] == ["content"]

    async def test_delete_note(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_character: Character,
        note_factory: Callable[..., Note],
    ) -> None:
        """Verify soft-deleting a note."""
        note = await note_factory(
            title="Note to Delete", content="Content", character_id=base_character.id
        )

        response = await client.delete(
            build_url(Characters.NOTE_DELETE, note_id=note.id),
            headers=token_company_admin,
        )

        assert response.status_code == HTTP_204_NO_CONTENT
        await note.sync()
        assert note.is_archived is True
        assert note.archive_date is not None


class TestAllNoteControllersSmoke:
    """Parametrized smoke tests to verify all note controller routes are working."""

    async def test_character_notes_smoke(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_character: Character,
    ) -> None:
        """Verify character notes create and list operations work."""
        # When we create a note
        create_response = await client.post(
            build_url(Characters.NOTE_CREATE, character_id=base_character.id),
            headers=token_company_admin,
            json={"title": "Smoke Test Note", "content": "Smoke test content"},
        )

        # Then it should be created successfully
        assert create_response.status_code == HTTP_201_CREATED
        note_id = create_response.json()["id"]

        # When we list notes
        list_response = await client.get(
            build_url(Characters.NOTES, character_id=base_character.id),
            headers=token_company_admin,
        )

        # Then the created note should appear in the list
        assert list_response.status_code == HTTP_200_OK
        note_ids = [item["id"] for item in list_response.json()["items"]]
        assert note_id in note_ids

    async def test_campaign_notes_smoke(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_campaign: Campaign,
    ) -> None:
        """Verify campaign notes create and list operations work."""
        # When we create a note
        create_response = await client.post(
            build_url(Campaigns.NOTE_CREATE, campaign_id=base_campaign.id),
            headers=token_company_admin,
            json={"title": "Campaign Smoke Note", "content": "Campaign smoke content"},
        )

        # Then it should be created successfully
        assert create_response.status_code == HTTP_201_CREATED
        note_id = create_response.json()["id"]

        # When we list notes
        list_response = await client.get(
            build_url(Campaigns.NOTES, campaign_id=base_campaign.id),
            headers=token_company_admin,
        )

        # Then the created note should appear in the list
        assert list_response.status_code == HTTP_200_OK
        note_ids = [item["id"] for item in list_response.json()["items"]]
        assert note_id in note_ids

    async def test_user_notes_smoke(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_user: User,
    ) -> None:
        """Verify user notes create and list operations work."""
        # When we create a note
        create_response = await client.post(
            build_url(Users.NOTE_CREATE, user_id=base_user.id),
            headers=token_company_admin,
            json={"title": "User Smoke Note", "content": "User smoke content"},
        )

        # Then it should be created successfully
        assert create_response.status_code == HTTP_201_CREATED
        note_id = create_response.json()["id"]

        # When we list notes
        list_response = await client.get(
            build_url(Users.LIST_NOTES, user_id=base_user.id),
            headers=token_company_admin,
        )

        # Then the created note should appear in the list
        assert list_response.status_code == HTTP_200_OK
        note_ids = [item["id"] for item in list_response.json()["items"]]
        assert note_id in note_ids

    async def test_book_notes_smoke(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_campaign_book: CampaignBook,
    ) -> None:
        """Verify campaign book notes create and list operations work."""
        # When we create a note
        create_response = await client.post(
            build_url(Campaigns.BOOK_NOTE_CREATE, book_id=base_campaign_book.id),
            headers=token_company_admin,
            json={"title": "Book Smoke Note", "content": "Book smoke content"},
        )

        # Then it should be created successfully
        assert create_response.status_code == HTTP_201_CREATED
        note_id = create_response.json()["id"]

        # When we list notes
        list_response = await client.get(
            build_url(Campaigns.BOOK_NOTES, book_id=base_campaign_book.id),
            headers=token_company_admin,
        )

        # Then the created note should appear in the list
        assert list_response.status_code == HTTP_200_OK
        note_ids = [item["id"] for item in list_response.json()["items"]]
        assert note_id in note_ids

    async def test_chapter_notes_smoke(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_admin: dict[str, str],
        base_campaign_chapter: CampaignChapter,
    ) -> None:
        """Verify campaign chapter notes create and list operations work."""
        # When we create a note
        create_response = await client.post(
            build_url(Campaigns.CHAPTER_NOTE_CREATE, chapter_id=base_campaign_chapter.id),
            headers=token_company_admin,
            json={"title": "Chapter Smoke Note", "content": "Chapter smoke content"},
        )

        # Then it should be created successfully
        assert create_response.status_code == HTTP_201_CREATED
        note_id = create_response.json()["id"]

        # When we list notes
        list_response = await client.get(
            build_url(Campaigns.CHAPTER_NOTES, chapter_id=base_campaign_chapter.id),
            headers=token_company_admin,
        )

        # Then the created note should appear in the list
        assert list_response.status_code == HTTP_200_OK
        note_ids = [item["id"] for item in list_response.json()["items"]]
        assert note_id in note_ids
