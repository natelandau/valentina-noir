"""Campaign book controller."""

from __future__ import annotations

from typing import Annotated

from litestar.controller import Controller
from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post, put
from litestar.params import Parameter
from pydantic import ValidationError as PydanticValidationError

from vapi.db.models import Campaign, CampaignBook
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CampaignService
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags
from vapi.utils.validation import raise_from_pydantic_validation_error

from . import dto
from .guards import user_can_manage_campaign


class CampaignBookController(Controller):
    """Campaign book controller."""

    tags = [APITags.CAMPAIGN_BOOKS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "user": Provide(deps.provide_user_by_id_and_company),
        "campaign": Provide(deps.provide_campaign_by_id),
        "book": Provide(deps.provide_campaign_book_by_id),
        "note": Provide(deps.provide_note_by_id),
    }
    guards = [developer_company_user_guard]
    return_dto = dto.BookDTO

    @get(
        path=urls.Campaigns.BOOKS,
        summary="List books",
        operation_id="listCampaignBooks",
        description="Retrieve a paginated list of books within a campaign.",
        cache=True,
    )
    async def list_books(
        self,
        *,
        campaign: Campaign,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[CampaignBook]:
        """List all books."""
        query = {
            "campaign_id": campaign.id,
            "is_archived": False,
        }
        count = await CampaignBook.find(query).count()
        books = await CampaignBook.find(query).skip(offset).limit(limit).sort("name").to_list()
        return OffsetPagination[CampaignBook](items=books, limit=limit, offset=offset, total=count)

    @get(
        path=urls.Campaigns.BOOK_DETAIL,
        summary="Get book",
        operation_id="getCampaignBook",
        description="Retrieve detailed information about a specific book.",
        cache=True,
    )
    async def get_book(self, *, book: CampaignBook) -> CampaignBook:
        """Get a book by ID."""
        return book

    @post(
        path=urls.Campaigns.BOOK_CREATE,
        summary="Create book",
        operation_id="createCampaignBook",
        description="Create a new book within a campaign. The book number is assigned automatically based on existing books. Requires storyteller privileges.",
        guards=[user_can_manage_campaign],
        dto=dto.PostBookDTO,
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def create_book(self, *, campaign: Campaign, data: DTOData[CampaignBook]) -> CampaignBook:
        """Create a book."""
        service = CampaignService()
        number = await service.get_next_book_number(campaign)

        book_data = data.create_instance(campaign_id=campaign.id, number=number)
        book = CampaignBook(**book_data.model_dump(exclude_unset=True))
        await book.save()

        return book

    @patch(
        path=urls.Campaigns.BOOK_UPDATE,
        summary="Update book",
        operation_id="updateCampaignBook",
        description="Modify a book's properties. Only include fields that need to be changed. Requires storyteller privileges.",
        guards=[user_can_manage_campaign],
        dto=dto.PatchBookDTO,
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def update_book(self, book: CampaignBook, data: DTOData[CampaignBook]) -> CampaignBook:
        """Update a book by ID."""
        updated_book = data.update_instance(book)
        try:
            await updated_book.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return updated_book

    @delete(
        path=urls.Campaigns.BOOK_DELETE,
        summary="Delete book",
        operation_id="deleteCampaignBook",
        description="Remove a book from a campaign. Remaining books will be automatically renumbered. Requires storyteller privileges.",
        guards=[user_can_manage_campaign],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def delete_book(self, book: CampaignBook) -> None:
        """Delete a book by ID."""
        service = CampaignService()
        await service.delete_book_and_renumber(book)

    @put(
        path=urls.Campaigns.BOOK_NUMBER,
        summary="Renumber book",
        operation_id="renumberCampaignBook",
        description="Change a book's position in the campaign sequence. Other books will be automatically reordered. Requires storyteller privileges.",
        guards=[user_can_manage_campaign],
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def renumber_book(
        self, book: CampaignBook, data: dto.BookChapterNumberDTO
    ) -> CampaignBook:
        """Renumber a book by ID."""
        service = CampaignService()
        await service.renumber_books(book=book, new_number=data.number)

        return book
