"""Dictionary controllers."""

from typing import Annotated

import msgspec
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter

from vapi.db.sql_models.company import Company
from vapi.db.sql_models.dictionary import DictionaryTerm
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import DictionaryService
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import docs
from .dto import DictionaryTermCreate, DictionaryTermPatch, DictionaryTermResponse


class DictionaryTermController(Controller):
    """Dictionary term controller."""

    tags = [APITags.DICTIONARY_TERMS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "dictionary_term": Provide(deps.provide_dictionary_term_by_id),
    }
    guards = [developer_company_user_guard]

    @get(
        path=urls.Dictionaries.LIST,
        summary="List dictionary terms",
        operation_id="listDictionaryTerms",
        description=docs.LIST_DICTIONARY_TERMS_DESCRIPTION,
        cache=True,
    )
    async def list_dictionary_terms(
        self,
        company: Company,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        term: Annotated[str, Parameter(description="Search for a term.")] | None = None,
    ) -> OffsetPagination[DictionaryTermResponse]:
        """List all dictionary terms."""
        service = DictionaryService()
        count, dictionary_terms = await service.list_all_dictionary_terms(
            company_id=company.id, limit=limit, offset=offset, term=term
        )
        return OffsetPagination(
            items=[DictionaryTermResponse.from_model(t) for t in dictionary_terms],
            limit=limit,
            offset=offset,
            total=count,
        )

    @get(
        path=urls.Dictionaries.DETAIL,
        summary="Get dictionary term",
        operation_id="getDictionaryTerm",
        description=docs.GET_DICTIONARY_TERM_DESCRIPTION,
        cache=True,
    )
    async def get_dictionary_term(self, dictionary_term: DictionaryTerm) -> DictionaryTermResponse:
        """Get a dictionary term by ID."""
        return DictionaryTermResponse.from_model(dictionary_term)

    @post(
        path=urls.Dictionaries.CREATE,
        summary="Create dictionary term",
        operation_id="createDictionaryTerm",
        description=docs.CREATE_DICTIONARY_TERM_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def create_dictionary_term(
        self, company: Company, data: DictionaryTermCreate
    ) -> DictionaryTermResponse:
        """Create a dictionary term."""
        dictionary_term = DictionaryTerm(
            term=data.term,
            definition=data.definition,
            link=data.link,
            synonyms=data.synonyms,
            company_id=company.id,
        )
        await dictionary_term.save()

        return DictionaryTermResponse.from_model(dictionary_term)

    @patch(
        path=urls.Dictionaries.UPDATE,
        summary="Update dictionary term",
        operation_id="updateDictionaryTerm",
        description=docs.UPDATE_DICTIONARY_TERM_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def update_dictionary_term(
        self, company: Company, dictionary_term: DictionaryTerm, data: DictionaryTermPatch
    ) -> DictionaryTermResponse:
        """Update a dictionary term by ID."""
        service = DictionaryService()
        service.verify_term_is_editable(dictionary_term, company_id=company.id)

        if not isinstance(data.term, msgspec.UnsetType):
            dictionary_term.term = data.term
        if not isinstance(data.definition, msgspec.UnsetType):
            dictionary_term.definition = data.definition
        if not isinstance(data.link, msgspec.UnsetType):
            dictionary_term.link = data.link
        if not isinstance(data.synonyms, msgspec.UnsetType):
            dictionary_term.synonyms = data.synonyms

        await dictionary_term.save()

        return DictionaryTermResponse.from_model(dictionary_term)

    @delete(
        path=urls.Dictionaries.DELETE,
        summary="Delete dictionary term",
        operation_id="deleteDictionaryTerm",
        description=docs.DELETE_DICTIONARY_TERM_DESCRIPTION,
        after_response=hooks.post_data_update_hook,
    )
    async def delete_dictionary_term(
        self, company: Company, dictionary_term: DictionaryTerm
    ) -> None:
        """Delete a dictionary term by ID."""
        service = DictionaryService()
        service.verify_term_is_editable(dictionary_term, company_id=company.id)

        dictionary_term.is_archived = True
        await dictionary_term.save()
