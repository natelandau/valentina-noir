"""Test dictionary controller."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import (
    HTTP_200_OK,
    HTTP_201_CREATED,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
)

from vapi.db.models import DictionaryTerm
from vapi.domain.services import DictionaryService
from vapi.domain.urls import Dictionaries

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.models import Company

pytestmark = pytest.mark.anyio


class TestDictionaryController:
    """Test dictionary controller."""

    async def test_list_dictionary_terms_with_results(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_user: dict[str, str],
        base_company: Company,
        dictionary_term_factory: Callable[[dict[str, Any]], DictionaryTerm],
        debug: Callable[[Any], None],
    ) -> None:
        """Test list dictionary terms."""
        await DictionaryTerm.delete_all()

        term1 = await dictionary_term_factory(
            term="Foo", definition="Foo is a bar.", company_id=base_company.id
        )
        term2 = await dictionary_term_factory(
            term="Bar", definition="Bar is a baz.", company_id=base_company.id
        )

        response = await client.get(build_url(Dictionaries.LIST), headers=token_company_user)
        assert response.status_code == HTTP_200_OK
        assert response.json() == {
            "items": [
                term2.model_dump(mode="json", exclude={"is_archived", "archive_date"}),
                term1.model_dump(mode="json", exclude={"is_archived", "archive_date"}),
            ],
            "limit": 10,
            "offset": 0,
            "total": 2,
        }

    async def test_get_dictionary_term(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_user: dict[str, str],
        base_company: Company,
        dictionary_term_factory: Callable[[dict[str, Any]], DictionaryTerm],
        debug: Callable[[Any], None],
    ) -> None:
        """Test get dictionary term."""
        term = await dictionary_term_factory(
            term="Foo", definition="Foo is a bar.", company_id=base_company.id
        )

        response = await client.get(
            build_url(Dictionaries.DETAIL, dictionary_term_id=term.id), headers=token_company_user
        )
        # debug(response.json())
        assert response.status_code == HTTP_200_OK
        assert response.json() == term.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )

    async def test_create_dictionary_term(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_user: dict[str, str],
        base_company: Company,
    ) -> None:
        """Test create dictionary term."""
        response = await client.post(
            build_url(Dictionaries.CREATE),
            headers=token_company_user,
            json={"term": "Foo", "definition": "  Foo is a bar.  ", "link": "https://example.com"},
        )
        assert response.status_code == HTTP_201_CREATED
        dictionary_term = await DictionaryTerm.get(response.json()["id"])
        assert response.json() == dictionary_term.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )
        assert dictionary_term.term == "foo"
        assert dictionary_term.definition == "Foo is a bar."
        assert dictionary_term.company_id == base_company.id
        assert dictionary_term.link == "https://example.com"
        assert dictionary_term.is_global == False

        # Cleanup
        await dictionary_term.delete()

    async def test_create_dictionary_term_invalid_data(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_user: dict[str, str],
        base_company: Company,
        debug: Callable[[Any], None],
    ) -> None:
        """Test create dictionary term invalid data."""
        response = await client.post(
            build_url(Dictionaries.CREATE),
            headers=token_company_user,
            json={"term": "something"},
        )
        # debug(response.json())

        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Must have either a definition or a link."

    async def test_update_dictionary_term(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_user: dict[str, str],
        base_company: Company,
        dictionary_term_factory: Callable[[dict[str, Any]], DictionaryTerm],
        mocker: Any,
    ) -> None:
        """Test update dictionary term."""
        term = await dictionary_term_factory(
            term="Foo",
            definition="Foo is a bar.",
            company_id=base_company.id,
            is_global=False,
        )
        spy = mocker.spy(DictionaryService, "verify_is_company_dictionary_term")

        response = await client.patch(
            build_url(Dictionaries.UPDATE, dictionary_term_id=term.id),
            headers=token_company_user,
            json={"term": "Bar", "definition": "Bar is a baz."},
        )
        assert spy.call_count == 1

        assert response.status_code == HTTP_200_OK
        await term.sync()
        assert response.json() == term.model_dump(
            mode="json", exclude={"is_archived", "archive_date"}
        )
        assert term.term == "bar"
        assert term.definition == "Bar is a baz."

    async def test_update_dictionary_term_invalid_data(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        token_company_user: dict[str, str],
        base_company: Company,
        dictionary_term_factory: Callable[[dict[str, Any]], DictionaryTerm],
        debug: Callable[[Any], None],
    ) -> None:
        """Test update dictionary term invalid data."""
        term = await dictionary_term_factory(
            term="Foo",
            definition="Foo is a bar.",
            company_id=base_company.id,
            link=None,
            is_global=False,
        )

        # When we update the dictionary term with invalid data
        response = await client.patch(
            build_url(Dictionaries.UPDATE, dictionary_term_id=term.id),
            headers=token_company_user,
            json={"definition": ""},
        )

        # Then we should get a 400 response
        assert response.status_code == HTTP_400_BAD_REQUEST
        assert response.json()["detail"] == "Must have either a definition or a link."

    async def test_delete_dictionary_term(
        self,
        client: AsyncClient,
        build_url: Callable[[str, Any], str],
        dictionary_term_factory: Callable[[dict[str, Any]], DictionaryTerm],
        token_company_user: dict[str, str],
        base_company: Company,
        mocker: Any,
    ) -> None:
        """Test delete dictionary term."""
        term = await dictionary_term_factory(
            term="Foo",
            definition="Foo is a bar.",
            company_id=base_company.id,
            is_global=False,
        )
        spy = mocker.spy(DictionaryService, "verify_is_company_dictionary_term")

        # When we delete the dictionary term
        response = await client.delete(
            build_url(Dictionaries.DELETE, dictionary_term_id=term.id), headers=token_company_user
        )

        # Then we should get a 204 response
        assert response.status_code == HTTP_204_NO_CONTENT
        # Then the dictionary term should be archived
        await term.sync()
        assert term.is_archived
        assert term.archive_date is not None
        # Then the verify_is_company_dictionary_term method should have been called
        assert spy.call_count == 1
