"""Unit tests for dictionary services."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from uuid_utils import uuid7

from vapi.constants import DictionarySourceType
from vapi.domain.services import DictionaryService
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.dictionary import DictionaryTerm

pytestmark = pytest.mark.anyio

# Unique synonym tag shared by all test-created terms to isolate them from
# bootstrap seed data when counting results.
_TEST_TAG = "zztestonly"


class TestVerifyTermIsEditable:
    """Test the verify_term_is_editable method."""

    async def test_not_editable_when_source_type_set(
        self,
        pg_company_factory: Callable[..., Company],
        pg_dictionary_term_factory: Callable[..., DictionaryTerm],
    ) -> None:
        """Verify term with source_type is not editable."""
        company = await pg_company_factory()
        term = await pg_dictionary_term_factory(
            company_id=company.id,
            source_type=DictionarySourceType.TRAIT,
            source_id=uuid7(),
        )
        with pytest.raises(
            ValidationError,
            match=r"You may not update dictionary terms that are not owned by your company",
        ):
            DictionaryService().verify_term_is_editable(term, company_id=company.id)

    async def test_not_editable_when_wrong_company(
        self,
        pg_company_factory: Callable[..., Company],
        pg_dictionary_term_factory: Callable[..., DictionaryTerm],
    ) -> None:
        """Verify term owned by different company is not editable."""
        company_a = await pg_company_factory()
        company_b = await pg_company_factory(name="Other Company", email="other@example.com")
        term = await pg_dictionary_term_factory(company_id=company_a.id)
        with pytest.raises(
            ValidationError,
            match=r"You may not update dictionary terms that are not owned by your company",
        ):
            DictionaryService().verify_term_is_editable(term, company_id=company_b.id)

    async def test_not_editable_when_no_company_id(
        self,
        pg_company_factory: Callable[..., Company],
        pg_dictionary_term_factory: Callable[..., DictionaryTerm],
    ) -> None:
        """Verify global term (no company_id) is not editable."""
        company = await pg_company_factory()
        term = await pg_dictionary_term_factory(company_id=None)
        with pytest.raises(
            ValidationError,
            match=r"You may not update dictionary terms that are not owned by your company",
        ):
            DictionaryService().verify_term_is_editable(term, company_id=company.id)

    async def test_editable_when_owned_by_company(
        self,
        pg_company_factory: Callable[..., Company],
        pg_dictionary_term_factory: Callable[..., DictionaryTerm],
    ) -> None:
        """Verify company-owned term without source_type is editable."""
        company = await pg_company_factory()
        term = await pg_dictionary_term_factory(company_id=company.id)
        result = DictionaryService().verify_term_is_editable(term, company_id=company.id)
        assert result is True


class TestListAllDictionaryTerms:
    """Test the list_all_dictionary_terms method."""

    async def test_returns_company_and_global_terms(
        self,
        pg_company_factory: Callable[..., Company],
        pg_dictionary_term_factory: Callable[..., DictionaryTerm],
    ) -> None:
        """Verify listing returns company-owned and global terms, excludes others."""
        # Use _TEST_TAG as a shared synonym to isolate test terms from bootstrap data
        company = await pg_company_factory()
        other_company = await pg_company_factory(name="Other Company", email="other@example.com")
        company_term = await pg_dictionary_term_factory(
            term="foo",
            definition="Foo is a bar.",
            company_id=company.id,
            synonyms=[_TEST_TAG],
        )
        global_term = await pg_dictionary_term_factory(
            term="bar",
            definition="Bar is a baz.",
            company_id=None,
            source_type=DictionarySourceType.TRAIT,
            source_id=uuid7(),
            synonyms=[_TEST_TAG],
        )
        await pg_dictionary_term_factory(
            term="baz",
            definition="Baz is a qux.",
            company_id=other_company.id,
            synonyms=[_TEST_TAG],
        )
        await pg_dictionary_term_factory(
            term="qux",
            definition="Qux is a quux.",
            company_id=company.id,
            is_archived=True,
            synonyms=[_TEST_TAG],
        )

        # Filter by _TEST_TAG synonym to count only test-created terms
        count, terms = await DictionaryService().list_all_dictionary_terms(
            company_id=company.id, limit=10, offset=0, term=_TEST_TAG
        )

        term_ids = [str(t.id) for t in terms]
        assert str(global_term.id) in term_ids
        assert str(company_term.id) in term_ids
        assert count == 2

    async def test_search_by_term(
        self,
        pg_company_factory: Callable[..., Company],
        pg_dictionary_term_factory: Callable[..., DictionaryTerm],
    ) -> None:
        """Verify search filters by term name or synonym."""
        company = await pg_company_factory()
        company_term = await pg_dictionary_term_factory(
            term="foo",
            definition="Foo is a bar.",
            company_id=company.id,
            synonyms=["bar"],
        )
        await pg_dictionary_term_factory(
            term="baz", definition="Baz is a qux.", company_id=company.id
        )
        global_term = await pg_dictionary_term_factory(
            term="bar",
            definition="Bar is a baz.",
            company_id=None,
            source_type=DictionarySourceType.TRAIT,
            source_id=uuid7(),
        )

        count, terms = await DictionaryService().list_all_dictionary_terms(
            company_id=company.id, limit=10, offset=0, term="bar"
        )

        term_ids = [str(t.id) for t in terms]
        assert str(global_term.id) in term_ids
        assert str(company_term.id) in term_ids
        assert count == 2

    async def test_pagination(
        self,
        pg_company_factory: Callable[..., Company],
        pg_dictionary_term_factory: Callable[..., DictionaryTerm],
    ) -> None:
        """Verify skip and limit work correctly."""
        company = await pg_company_factory()
        # Use _TEST_TAG synonym to scope results to exactly these 2 test-created terms
        await pg_dictionary_term_factory(
            term="alpha", definition="First.", company_id=company.id, synonyms=[_TEST_TAG]
        )
        term_b = await pg_dictionary_term_factory(
            term="beta", definition="Second.", company_id=company.id, synonyms=[_TEST_TAG]
        )

        count, terms = await DictionaryService().list_all_dictionary_terms(
            company_id=company.id, limit=1, offset=1, term=_TEST_TAG
        )

        assert count == 2
        assert len(terms) == 1
        assert str(terms[0].id) == str(term_b.id)
