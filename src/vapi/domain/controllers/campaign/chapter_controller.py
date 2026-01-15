"""Campaign chapter controller."""

from __future__ import annotations

from typing import Annotated

from litestar.controller import Controller
from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post, put
from litestar.params import Parameter
from pydantic import ValidationError as PydanticValidationError

from vapi.db.models import CampaignBook, CampaignChapter
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CampaignService
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags
from vapi.utils.validation import raise_from_pydantic_validation_error

from . import dto
from .guards import user_can_manage_campaign


class CampaignChapterController(Controller):
    """Campaign chapter controller."""

    tags = [APITags.CAMPAIGN_CHAPTERS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "campaign": Provide(deps.provide_campaign_by_id),
        "book": Provide(deps.provide_campaign_book_by_id),
        "chapter": Provide(deps.provide_campaign_chapter_by_id),
        "note": Provide(deps.provide_note_by_id),
    }
    guards = [developer_company_user_guard]
    return_dto = dto.ChapterDTO

    @get(
        path=urls.Campaigns.CHAPTERS,
        summary="List chapters",
        operation_id="listCampaignChapters",
        description="Retrieve a paginated list of chapters within a book. Chapters represent individual game sessions or story segments.",
        cache=True,
    )
    async def list_chapters(
        self,
        *,
        book: CampaignBook,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[CampaignChapter]:
        """List all chapters."""
        query = {
            "book_id": book.id,
            "is_archived": False,
        }
        count = await CampaignChapter.find(query).count()
        chapters = (
            await CampaignChapter.find(query).skip(offset).limit(limit).sort("name").to_list()
        )
        return OffsetPagination(items=chapters, limit=limit, offset=offset, total=count)

    @get(
        path=urls.Campaigns.CHAPTER_DETAIL,
        summary="Get chapter",
        operation_id="getCampaignChapter",
        description="Retrieve detailed information about a specific chapter.",
        cache=True,
    )
    async def get_chapter(self, *, chapter: CampaignChapter) -> CampaignChapter:
        """Get a chapter by ID."""
        return chapter

    @post(
        path=urls.Campaigns.CHAPTER_CREATE,
        summary="Create chapter",
        operation_id="createCampaignChapter",
        description="Create a new chapter within a book. The chapter number is assigned automatically based on existing chapters. Requires storyteller privileges.",
        guards=[user_can_manage_campaign],
        dto=dto.PostChapterDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def create_chapter(
        self, *, book: CampaignBook, data: DTOData[CampaignChapter]
    ) -> CampaignChapter:
        """Create a chapter."""
        service = CampaignService()
        number = await service.get_next_chapter_number(book)

        chapter_data = data.create_instance(book_id=book.id, number=number)
        chapter = CampaignChapter(**chapter_data.model_dump(exclude_unset=True))
        await chapter.save()
        return chapter

    @patch(
        path=urls.Campaigns.CHAPTER_UPDATE,
        summary="Update chapter",
        operation_id="updateCampaignChapter",
        description="Modify a chapter's properties. Only include fields that need to be changed. Requires storyteller privileges.",
        guards=[user_can_manage_campaign],
        dto=dto.PatchChapterDTO,
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def update_chapter(
        self, chapter: CampaignChapter, data: DTOData[CampaignChapter]
    ) -> CampaignChapter:
        """Update a chapter by ID."""
        updated_chapter = data.update_instance(chapter)
        try:
            await updated_chapter.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return updated_chapter

    @delete(
        path=urls.Campaigns.CHAPTER_DELETE,
        summary="Delete chapter",
        operation_id="deleteCampaignChapter",
        description="Remove a chapter from a book. Remaining chapters will be automatically renumbered. Requires storyteller privileges.",
        guards=[user_can_manage_campaign],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def delete_chapter(self, chapter: CampaignChapter) -> None:
        """Delete a chapter by ID."""
        service = CampaignService()
        await service.delete_chapter_and_renumber(chapter)

    @put(
        path=urls.Campaigns.CHAPTER_NUMBER,
        summary="Renumber chapter",
        operation_id="renumberCampaignChapter",
        description="Change a chapter's position within a book. Other chapters will be automatically reordered. Requires storyteller privileges.",
        guards=[user_can_manage_campaign],
        after_response=hooks.audit_log_and_delete_api_key_cache,
    )
    async def renumber_chapter(
        self, chapter: CampaignChapter, data: dto.BookChapterNumberDTO
    ) -> CampaignChapter:
        """Renumber a chapter by ID."""
        service = CampaignService()
        await service.renumber_chapters(chapter=chapter, new_number=data.number)

        return chapter
