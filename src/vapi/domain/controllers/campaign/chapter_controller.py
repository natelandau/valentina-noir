"""Campaign chapter controller."""

import asyncio
from typing import Annotated

import msgspec
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post, put
from litestar.params import Parameter

from vapi.db.sql_models.campaign import CampaignBook, CampaignChapter
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CampaignService
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import docs
from .dto import (
    BookChapterNumber,
    CampaignChapterCreate,
    CampaignChapterPatch,
    CampaignChapterResponse,
)
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
        "developer": Provide(deps.provide_developer_from_request),
    }
    guards = [developer_company_user_guard]

    @get(
        path=urls.Campaigns.CHAPTERS,
        summary="List chapters",
        operation_id="listCampaignChapters",
        description=docs.LIST_CHAPTERS_DESCRIPTION,
        cache=True,
    )
    async def list_chapters(
        self,
        *,
        book: CampaignBook,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[CampaignChapterResponse]:
        """List all chapters."""
        qs = CampaignChapter.filter(book_id=book.id, is_archived=False)
        count, chapters = await asyncio.gather(
            qs.count(),
            qs.order_by("number").offset(offset).limit(limit),
        )
        return OffsetPagination(
            items=[CampaignChapterResponse.from_model(ch) for ch in chapters],
            limit=limit,
            offset=offset,
            total=count,
        )

    @get(
        path=urls.Campaigns.CHAPTER_DETAIL,
        summary="Get chapter",
        operation_id="getCampaignChapter",
        description=docs.GET_CHAPTER_DESCRIPTION,
        cache=True,
    )
    async def get_chapter(self, *, chapter: CampaignChapter) -> CampaignChapterResponse:
        """Get a chapter by ID."""
        return CampaignChapterResponse.from_model(chapter)

    @post(
        path=urls.Campaigns.CHAPTER_CREATE,
        summary="Create chapter",
        operation_id="createCampaignChapter",
        description=docs.CREATE_CHAPTER_DESCRIPTION,
        guards=[user_can_manage_campaign],
        after_response=hooks.post_data_update_hook,
    )
    async def create_chapter(
        self, *, book: CampaignBook, data: CampaignChapterCreate
    ) -> CampaignChapterResponse:
        """Create a chapter."""
        service = CampaignService()
        number = await service.get_next_chapter_number(book)
        chapter = await CampaignChapter.create(
            name=data.name,
            description=data.description,
            book=book,
            number=number,
        )
        return CampaignChapterResponse.from_model(chapter)

    @patch(
        path=urls.Campaigns.CHAPTER_UPDATE,
        summary="Update chapter",
        operation_id="updateCampaignChapter",
        description=docs.UPDATE_CHAPTER_DESCRIPTION,
        guards=[user_can_manage_campaign],
        after_response=hooks.post_data_update_hook,
    )
    async def update_chapter(
        self, chapter: CampaignChapter, data: CampaignChapterPatch
    ) -> CampaignChapterResponse:
        """Update a chapter by ID."""
        if not isinstance(data.name, msgspec.UnsetType):
            chapter.name = data.name
        if not isinstance(data.description, msgspec.UnsetType):
            chapter.description = data.description
        await chapter.save()
        return CampaignChapterResponse.from_model(chapter)

    @delete(
        path=urls.Campaigns.CHAPTER_DELETE,
        summary="Delete chapter",
        operation_id="deleteCampaignChapter",
        description=docs.DELETE_CHAPTER_DESCRIPTION,
        guards=[user_can_manage_campaign],
        after_response=hooks.post_data_update_hook,
    )
    async def delete_chapter(self, chapter: CampaignChapter) -> None:
        """Delete a chapter by ID."""
        service = CampaignService()
        await service.delete_chapter_and_renumber(chapter)

    @put(
        path=urls.Campaigns.CHAPTER_NUMBER,
        summary="Renumber chapter",
        operation_id="renumberCampaignChapter",
        description=docs.RENUMBER_CHAPTER_DESCRIPTION,
        guards=[user_can_manage_campaign],
        after_response=hooks.post_data_update_hook,
    )
    async def renumber_chapter(
        self, chapter: CampaignChapter, data: BookChapterNumber
    ) -> CampaignChapterResponse:
        """Renumber a chapter by ID."""
        service = CampaignService()
        chapter = await service.renumber_chapters(chapter=chapter, new_number=data.number)
        return CampaignChapterResponse.from_model(chapter)
