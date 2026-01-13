"""Dictionary controllers."""

from __future__ import annotations

from typing import Annotated

from litestar.controller import Controller
from litestar.di import Provide
from litestar.dto import DTOData  # noqa: TC002
from litestar.handlers import delete, get, patch, post
from litestar.params import Parameter
from pydantic import ValidationError as PydanticValidationError

from vapi.db.models import Company, DictionaryTerm
from vapi.domain import deps, hooks, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import DictionaryService
from vapi.domain.utils import patch_internal_objects
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags
from vapi.utils.validation import raise_from_pydantic_validation_error

from . import dto


class DictionaryTermController(Controller):
    """Dictionary term controller."""

    tags = [APITags.DICTIONARY_TERMS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
        "dictionary_term": Provide(deps.provide_dictionary_term_by_id),
    }
    guards = [developer_company_user_guard]
    return_dto = dto.DictionaryTermResponseDTO

    @get(
        path=urls.Dictionaries.LIST,
        summary="List dictionary terms",
        operation_id="listDictionaryTerms",
        description="Retrieve a paginated list of dictionary terms for a company. Optionally search by term name or synonym. Terms provide definitions for game concepts and lore.",
        cache=True,
    )
    async def list_dictionary_terms(
        self,
        company: Company,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        term: Annotated[str, Parameter(description="Search for a term.")] | None = None,
    ) -> OffsetPagination[DictionaryTerm]:
        """List all dictionary terms."""
        service = DictionaryService()
        count, dictionary_terms = await service.list_all_dictionary_terms(
            company=company, limit=limit, offset=offset, term=term
        )
        return OffsetPagination(
            dictionary_terms,
            limit=limit,
            offset=offset,
            total=count,
        )

    @get(
        path=urls.Dictionaries.DETAIL,
        summary="Get dictionary term",
        operation_id="getDictionaryTerm",
        description="Retrieve a specific dictionary term including its definition and synonyms.",
        cache=True,
    )
    async def get_dictionary_term(self, dictionary_term: DictionaryTerm) -> DictionaryTerm:
        """Get a dictionary term by ID."""
        return dictionary_term

    @post(
        path=urls.Dictionaries.CREATE,
        summary="Create dictionary term",
        operation_id="createDictionaryTerm",
        description="Add a new term to the company's dictionary. Include the term, definition, and optional synonyms for discovery.",
        dto=dto.DictionaryTermPostDTO,
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def create_dictionary_term(
        self, company: Company, data: DTOData[DictionaryTerm]
    ) -> DictionaryTerm:
        """Create a dictionary term."""
        try:
            dictionary_term_data = data.create_instance(company_id=company.id)
            dictionary_term = DictionaryTerm(**dictionary_term_data.model_dump(exclude_unset=True))
            await dictionary_term.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return dictionary_term

    @patch(
        path=urls.Dictionaries.UPDATE,
        summary="Update dictionary term",
        operation_id="updateDictionaryTerm",
        description="Modify a dictionary term's definition or synonyms. Only include fields that need to be changed.",
        dto=dto.DictionaryTermPatchDTO,
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def update_dictionary_term(
        self, dictionary_term: DictionaryTerm, data: DTOData[DictionaryTerm]
    ) -> DictionaryTerm:
        """Update a dictionary term by ID."""
        service = DictionaryService()
        service.verify_is_company_dictionary_term(dictionary_term)

        dictionary_term, data = await patch_internal_objects(original=dictionary_term, data=data)
        try:
            updated_dictionary_term = data.update_instance(dictionary_term)
            await updated_dictionary_term.save()
        except PydanticValidationError as e:
            raise_from_pydantic_validation_error(e)

        return updated_dictionary_term

    @delete(
        path=urls.Dictionaries.DELETE,
        summary="Delete dictionary term",
        operation_id="deleteDictionaryTerm",
        description="Remove a term from the company's dictionary. This action cannot be undone.",
        after_response=hooks.audit_log_and_delete_eapi_key_cache,
    )
    async def delete_dictionary_term(self, dictionary_term: DictionaryTerm) -> None:
        """Delete a dictionary term by ID."""
        service = DictionaryService()
        service.verify_is_company_dictionary_term(dictionary_term)

        dictionary_term.is_archived = True
        await dictionary_term.save()
