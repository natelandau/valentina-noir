"""Test dictionary controller."""

from typing import TYPE_CHECKING, Any

import pytest
from litestar.status_codes import (
    HTTP_201_CREATED,
    HTTP_400_BAD_REQUEST,
)

from vapi.db.sql_models.company import Company as PgCompany
from vapi.domain.urls import Dictionaries

if TYPE_CHECKING:
    from collections.abc import Callable

    from httpx import AsyncClient

    from vapi.db.sql_models.developer import Developer as PgDeveloper
    from vapi.db.sql_models.dictionary import DictionaryTerm

pytestmark = pytest.mark.anyio


class TestDictionaryController:
    """Test dictionary controller."""

    async def test_create_dictionary_term_invalid_data(
        self,
        client: "AsyncClient",
        build_url: "Callable[[str, Any], str]",
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: "PgDeveloper",
    ) -> None:
        """Verify creating a term without definition or link returns 400."""
        # When we create a term with no definition or link
        response = await client.post(
            build_url(Dictionaries.CREATE, company_id=pg_mirror_company.id),
            headers=token_company_user,
            json={"term": "something"},
        )

        # Then we get a 400
        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_list_dictionary_terms_with_results(
        self,
        client: "AsyncClient",
        build_url: "Callable[[str, Any], str]",
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: "PgDeveloper",
        pg_dictionary_term_factory: "Callable[..., DictionaryTerm]",
    ) -> None:
        """Verify listing dictionary terms returns company and global terms."""
        # Given two global terms
        term1 = await pg_dictionary_term_factory(
            term="Foo", definition="Foo is a bar.", company_id=None
        )
        await pg_dictionary_term_factory(term="Bar", definition="Bar is a baz.", company_id=None)

        # When we list dictionary terms with a high limit to include all
        response = await client.get(
            build_url(Dictionaries.LIST, company_id=pg_mirror_company.id),
            headers=token_company_user,
            params={"limit": 100, "term": "foo"},
        )

        # Then we get a 200 with the matching term
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        returned_ids = {item["id"] for item in data["items"]}
        assert str(term1.id) in returned_ids

    async def test_get_dictionary_term(
        self,
        client: "AsyncClient",
        build_url: "Callable[[str, Any], str]",
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: "PgDeveloper",
        pg_dictionary_term_factory: "Callable[..., DictionaryTerm]",
    ) -> None:
        """Verify getting a single dictionary term by ID."""
        # Given a global term
        term = await pg_dictionary_term_factory(
            term="Foo", definition="Foo is a bar.", company_id=None
        )

        # When we get the term
        response = await client.get(
            build_url(
                Dictionaries.DETAIL,
                company_id=pg_mirror_company.id,
                dictionary_term_id=term.id,
            ),
            headers=token_company_user,
        )

        # Then we get a 200 with the term data
        assert response.status_code == 200
        assert response.json()["id"] == str(term.id)
        assert response.json()["term"] == "foo"

    async def test_create_dictionary_term(
        self,
        client: "AsyncClient",
        build_url: "Callable[[str, Any], str]",
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: "PgDeveloper",
    ) -> None:
        """Verify creating a dictionary term returns 201 with correct data."""
        # When we create a term
        response = await client.post(
            build_url(Dictionaries.CREATE, company_id=pg_mirror_company.id),
            headers=token_company_user,
            json={"term": "Foo", "definition": "  Foo is a bar.  ", "link": "https://example.com"},
        )

        # Then we get a 201 with the created term
        assert response.status_code == HTTP_201_CREATED
        created = response.json()
        assert created["term"] == "foo"
        assert created["definition"] == "  Foo is a bar.  "
        assert created["link"] == "https://example.com"
        assert created["source_type"] is None

    async def test_update_dictionary_term(
        self,
        client: "AsyncClient",
        build_url: "Callable[[str, Any], str]",
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: "PgDeveloper",
        pg_dictionary_term_factory: "Callable[..., DictionaryTerm]",
        mocker: Any,
    ) -> None:
        """Verify updating a dictionary term."""
        from vapi.domain.services import DictionaryService

        # Given a company-owned term (editable by the company)
        term = await pg_dictionary_term_factory(
            term="Foo", definition="Foo is a bar.", company_id=str(pg_mirror_company.id)
        )
        spy = mocker.spy(DictionaryService, "verify_term_is_editable")

        # When we update the term
        response = await client.patch(
            build_url(
                Dictionaries.UPDATE,
                company_id=pg_mirror_company.id,
                dictionary_term_id=term.id,
            ),
            headers=token_company_user,
            json={"term": "Bar", "definition": "Bar is a baz."},
        )

        # Then we get a 200 with updated data
        assert spy.call_count == 1
        assert response.status_code == 200
        assert response.json()["term"] == "bar"
        assert response.json()["definition"] == "Bar is a baz."

    async def test_update_dictionary_term_invalid_data(
        self,
        client: "AsyncClient",
        build_url: "Callable[[str, Any], str]",
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: "PgDeveloper",
        pg_dictionary_term_factory: "Callable[..., DictionaryTerm]",
    ) -> None:
        """Verify updating a term to have no definition or link returns 400."""
        # Given a company-owned term with a definition but no link
        term = await pg_dictionary_term_factory(
            term="Foo", definition="Foo is a bar.", company_id=str(pg_mirror_company.id), link=None
        )

        # When we clear the definition
        response = await client.patch(
            build_url(
                Dictionaries.UPDATE,
                company_id=pg_mirror_company.id,
                dictionary_term_id=term.id,
            ),
            headers=token_company_user,
            json={"definition": ""},
        )

        # Then we get a 400
        assert response.status_code == HTTP_400_BAD_REQUEST

    async def test_delete_dictionary_term(
        self,
        client: "AsyncClient",
        build_url: "Callable[[str, Any], str]",
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: "PgDeveloper",
        pg_dictionary_term_factory: "Callable[..., DictionaryTerm]",
        token_company_user: dict[str, str],
        mocker: Any,
    ) -> None:
        """Verify deleting a dictionary term soft-deletes it."""
        from vapi.domain.services import DictionaryService

        # Given a company-owned term (editable by the company)
        term = await pg_dictionary_term_factory(
            term="Foo", definition="Foo is a bar.", company_id=str(pg_mirror_company.id)
        )
        spy = mocker.spy(DictionaryService, "verify_term_is_editable")

        # When we delete the term
        response = await client.delete(
            build_url(
                Dictionaries.DELETE,
                company_id=pg_mirror_company.id,
                dictionary_term_id=term.id,
            ),
            headers=token_company_user,
        )

        # Then we get 204 and the term is archived
        assert response.status_code == 204
        await term.refresh_from_db()
        assert term.is_archived is True
        assert term.archive_date is not None
        assert spy.call_count == 1

    async def test_get_term_from_different_company_returns_404(
        self,
        client: "AsyncClient",
        build_url: "Callable[[str, Any], str]",
        token_company_user: dict[str, str],
        pg_mirror_company: PgCompany,
        pg_mirror_company_user: "PgDeveloper",
        pg_dictionary_term_factory: "Callable[..., DictionaryTerm]",
        pg_company_factory: "Callable[..., Any]",
    ) -> None:
        """Verify accessing a term from a different company returns 404."""
        # Given a term owned by a different company
        other_company = await pg_company_factory()
        term = await pg_dictionary_term_factory(
            term="Secret", definition="Not yours.", company_id=other_company.id
        )

        # When we try to get it with our company credentials
        response = await client.get(
            build_url(
                Dictionaries.DETAIL,
                company_id=pg_mirror_company.id,
                dictionary_term_id=term.id,
            ),
            headers=token_company_user,
        )

        # Then we get a 404
        assert response.status_code == 404
