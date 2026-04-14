"""Campaign book controller."""

import asyncio
from typing import Annotated

from litestar import Request
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post, put
from litestar.params import Parameter

from vapi.db.sql_models.campaign import Campaign, CampaignBook
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CampaignService
from vapi.lib.detail_includes import apply_includes
from vapi.lib.guards import developer_company_user_guard
from vapi.lib.patch import apply_patch
from vapi.openapi.tags import APITags

from . import docs
from .dto import (
    BookChapterNumber,
    BookInclude,
    CampaignBookCreate,
    CampaignBookDetailResponse,
    CampaignBookPatch,
    CampaignBookResponse,
    get_book_include_prefetch_map,
)
from .guards import user_can_manage_campaign


class CampaignBookController(Controller):
    """Campaign book controller."""

    tags = [APITags.CAMPAIGN_BOOKS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_target_user),
        "campaign": Provide(deps.provide_campaign_by_id),
        "book": Provide(deps.provide_campaign_book_by_id),
        "developer": Provide(deps.provide_developer_from_request),
    }
    guards = [developer_company_user_guard]

    @get(
        path=urls.Campaigns.BOOKS,
        summary="List books",
        operation_id="listCampaignBooks",
        description=docs.LIST_BOOKS_DESCRIPTION,
        cache=True,
    )
    async def list_books(
        self,
        *,
        campaign: Campaign,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[CampaignBookResponse]:
        """List all books."""
        qs = CampaignBook.filter(campaign_id=campaign.id, is_archived=False)
        count, books = await asyncio.gather(
            qs.count(),
            qs.order_by("number").offset(offset).limit(limit),
        )
        return OffsetPagination(
            items=[CampaignBookResponse.from_model(b) for b in books],
            limit=limit,
            offset=offset,
            total=count,
        )

    @get(
        path=urls.Campaigns.BOOK_DETAIL,
        summary="Get book",
        operation_id="getCampaignBook",
        description=docs.GET_BOOK_DESCRIPTION,
        cache=True,
    )
    async def get_book(
        self,
        *,
        book: CampaignBook,
        include: list[BookInclude] | None = None,
    ) -> CampaignBookDetailResponse:
        """Get a book by ID with optional embedded children."""
        requested = await apply_includes(book, include, get_book_include_prefetch_map())
        return CampaignBookDetailResponse.from_model(book, requested)

    @post(
        path=urls.Campaigns.BOOK_CREATE,
        summary="Create book",
        operation_id="createCampaignBook",
        description=docs.CREATE_BOOK_DESCRIPTION,
        guards=[user_can_manage_campaign],
        after_response=hooks.post_data_update_hook,
    )
    async def create_book(
        self, *, campaign: Campaign, data: CampaignBookCreate, request: Request
    ) -> CampaignBookResponse:
        """Create a book."""
        service = CampaignService()
        number = await service.get_next_book_number(campaign)
        book = await CampaignBook.create(
            name=data.name,
            description=data.description,
            campaign=campaign,
            number=number,
        )
        request.state.audit_description = (
            f"Create book '{book.number}: {book.name}' for campaign '{campaign.name}'"
        )
        return CampaignBookResponse.from_model(book)

    @patch(
        path=urls.Campaigns.BOOK_UPDATE,
        summary="Update book",
        operation_id="updateCampaignBook",
        description=docs.UPDATE_BOOK_DESCRIPTION,
        guards=[user_can_manage_campaign],
        after_response=hooks.post_data_update_hook,
    )
    async def update_book(
        self, book: CampaignBook, data: CampaignBookPatch, request: Request
    ) -> CampaignBookResponse:
        """Update a book by ID."""
        changes = apply_patch(book, data)
        request.state.audit_changes = changes
        request.state.audit_description = f"Update book '{book.number}: {book.name}'"
        await book.save()
        return CampaignBookResponse.from_model(book)

    @delete(
        path=urls.Campaigns.BOOK_DELETE,
        summary="Delete book",
        operation_id="deleteCampaignBook",
        description=docs.DELETE_BOOK_DESCRIPTION,
        guards=[user_can_manage_campaign],
        after_response=hooks.post_data_update_hook,
    )
    async def delete_book(self, book: CampaignBook, request: Request) -> None:
        """Delete a book by ID."""
        service = CampaignService()
        await service.delete_book_and_renumber(book)
        request.state.audit_description = f"Delete book '{book.number}: {book.name}'"

    @put(
        path=urls.Campaigns.BOOK_NUMBER,
        summary="Renumber book",
        operation_id="renumberCampaignBook",
        description=docs.RENUMBER_BOOK_DESCRIPTION,
        guards=[user_can_manage_campaign],
        after_response=hooks.post_data_update_hook,
    )
    async def renumber_book(
        self, book: CampaignBook, data: BookChapterNumber, request: Request
    ) -> CampaignBookResponse:
        """Renumber a book by ID."""
        old_number = book.number
        service = CampaignService()
        book = await service.renumber_books(book=book, new_number=data.number)
        if old_number != data.number:
            request.state.audit_changes = {"number": {"old": old_number, "new": data.number}}
        request.state.audit_description = (
            f"Renumber book '{book.name}' from {old_number} to {data.number}"
        )
        return CampaignBookResponse.from_model(book)
