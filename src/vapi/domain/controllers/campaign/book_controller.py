"""Campaign book controller."""

import asyncio
from typing import Annotated

import msgspec
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post, put
from litestar.params import Parameter

from vapi.db.sql_models.campaign import Campaign, CampaignBook
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CampaignService
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import docs
from .dto import (
    BookChapterNumber,
    CampaignBookCreate,
    CampaignBookPatch,
    CampaignBookResponse,
)
from .guards import user_can_manage_campaign


class CampaignBookController(Controller):
    """Campaign book controller."""

    tags = [APITags.CAMPAIGN_BOOKS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
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
    async def get_book(self, *, book: CampaignBook) -> CampaignBookResponse:
        """Get a book by ID."""
        return CampaignBookResponse.from_model(book)

    @post(
        path=urls.Campaigns.BOOK_CREATE,
        summary="Create book",
        operation_id="createCampaignBook",
        description=docs.CREATE_BOOK_DESCRIPTION,
        guards=[user_can_manage_campaign],
        after_response=hooks.post_data_update_hook,
    )
    async def create_book(
        self, *, campaign: Campaign, data: CampaignBookCreate
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
        self, book: CampaignBook, data: CampaignBookPatch
    ) -> CampaignBookResponse:
        """Update a book by ID."""
        if not isinstance(data.name, msgspec.UnsetType):
            book.name = data.name
        if not isinstance(data.description, msgspec.UnsetType):
            book.description = data.description
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
    async def delete_book(self, book: CampaignBook) -> None:
        """Delete a book by ID."""
        service = CampaignService()
        await service.delete_book_and_renumber(book)

    @put(
        path=urls.Campaigns.BOOK_NUMBER,
        summary="Renumber book",
        operation_id="renumberCampaignBook",
        description=docs.RENUMBER_BOOK_DESCRIPTION,
        guards=[user_can_manage_campaign],
        after_response=hooks.post_data_update_hook,
    )
    async def renumber_book(
        self, book: CampaignBook, data: BookChapterNumber
    ) -> CampaignBookResponse:
        """Renumber a book by ID."""
        service = CampaignService()
        book = await service.renumber_books(book=book, new_number=data.number)
        return CampaignBookResponse.from_model(book)
