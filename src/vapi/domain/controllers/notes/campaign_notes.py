"""Campaign notes controller."""

from __future__ import annotations

from typing import Annotated

from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.models import Campaign, Company, Note  # noqa: TC001
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination  # noqa: TC001
from vapi.openapi.tags import APITags

from . import dto
from .base import BaseNoteController


class CampaignNoteController(BaseNoteController):
    """Campaign notes controller."""

    tags = [APITags.CAMPAIGNS_NOTES.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "campaign": Provide(deps.provide_campaign_by_id),
        "note": Provide(deps.provide_note_by_id),
    }

    @property
    def parent_name(self) -> str:
        """Return the parent entity name."""
        return "campaign"

    @get(
        path=urls.Campaigns.NOTES,
        summary="List campaign notes",
        operation_id="listCampaignNotes",
        description="Retrieve a paginated list of notes attached to a campaign. Notes can contain session summaries, plot points, or other campaign-level information.",
        cache=True,
    )
    async def list_campaign_notes(
        self,
        *,
        campaign: Campaign,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[Note]:
        """List all campaign notes."""
        return await self._list_notes(campaign.id, limit, offset)

    @get(
        path=urls.Campaigns.NOTE_DETAIL,
        summary="Get campaign note",
        operation_id="getCampaignNote",
        description="Retrieve a specific note attached to a campaign.",
        cache=True,
    )
    async def get_campaign_note(self, *, note: Note) -> Note:
        """Get a campaign note by ID."""
        return await self._get_note(note)

    @post(
        path=urls.Campaigns.NOTE_CREATE,
        summary="Create campaign note",
        operation_id="createCampaignNote",
        description="Attach a new note to a campaign. Notes support markdown formatting for rich text content.",
        dto=dto.NotePostDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def create_campaign_note(
        self, *, company: Company, campaign: Campaign, data: DTOData[Note]
    ) -> Note:
        """Create a campaign note."""
        return await self._create_note(company_id=company.id, parent_id=campaign.id, data=data)

    @patch(
        path=urls.Campaigns.NOTE_UPDATE,
        summary="Update campaign note",
        operation_id="updateCampaignNote",
        description="Modify a campaign note's content. Only include fields that need to be changed.",
        dto=dto.NotePatchDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def update_campaign_note(self, note: Note, data: DTOData[Note]) -> Note:
        """Update a campaign note by ID."""
        return await self._update_note(note, data)

    @delete(
        path=urls.Campaigns.NOTE_DELETE,
        summary="Delete campaign note",
        operation_id="deleteCampaignNote",
        description="Remove a note from a campaign. This action cannot be undone.",
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def delete_campaign_note(self, *, note: Note) -> None:
        """Delete a campaign note by ID."""
        await self._delete_note(note)
