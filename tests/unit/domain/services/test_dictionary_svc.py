"""Unit tests for dictionary services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from beanie import PydanticObjectId

from vapi.db.models import Company, DictionaryTerm
from vapi.domain.services import DictionaryService
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


class TestDictionaryService:
    """Test the dictionary service."""

    def test_verify_is_company_dictionary_false(self) -> None:
        """Test the verify_is_company_dictionary_term method."""
        dictionary_term = DictionaryTerm(term="Foo", definition="Foo is a bar.", is_global=True)
        with pytest.raises(ValidationError, match=r"You may only update company dictionary terms"):
            DictionaryService().verify_is_company_dictionary_term(dictionary_term)

    def test_verify_is_company_dictionary_true(self) -> None:
        """Test the verify_is_company_dictionary_term method."""
        dictionary_term = DictionaryTerm(
            term="Foo",
            definition="Foo is a bar.",
            is_global=False,
            company_id=PydanticObjectId(),
        )
        assert DictionaryService().verify_is_company_dictionary_term(dictionary_term)

    async def test_list_all_dictionary_terms(
        self, company_factory: Callable[[], Company], debug: Callable[[Any], None]
    ) -> None:
        """Test the list_all_dictionary_terms method."""
        await DictionaryTerm.delete_all()
        company = await company_factory()
        company_term = await DictionaryTerm(
            term="Foo",
            definition="Foo is a bar.",
            company_id=company.id,
            is_global=False,
        ).insert()
        global_term = await DictionaryTerm(
            term="Bar",
            definition="Bar is a baz.",
            is_global=True,
        ).insert()
        non_company_term = await DictionaryTerm(
            term="Baz",
            definition="Baz is a qux.",
            is_global=False,
            company_id=PydanticObjectId(),
        ).insert()
        archived_term = await DictionaryTerm(
            term="Qux",
            definition="Qux is a quux.",
            company_id=company.id,
            is_archived=True,
        ).insert()

        # When we list all dictionary terms
        count, dictionary_terms = await DictionaryService().list_all_dictionary_terms(
            company=company, limit=10, offset=0
        )
        # Then we should get the correct count and dictionary terms
        assert non_company_term.id not in [x.id for x in dictionary_terms]
        assert archived_term.id not in [x.id for x in dictionary_terms]
        assert global_term.id in [x.id for x in dictionary_terms]
        assert company_term.id in [x.id for x in dictionary_terms]

        assert count == 2
        assert dictionary_terms == [global_term, company_term]

    async def test_list_all_dictionary_terms_with_term(
        self, company_factory: Callable[[], Company], debug: Callable[[Any], None]
    ) -> None:
        """Test the list_all_dictionary_terms method."""
        await DictionaryTerm.delete_all()
        company = await company_factory()
        company_term = await DictionaryTerm(
            term="Foo",
            definition="Foo is a bar.",
            company_id=company.id,
            synonyms=["Bar"],
        ).insert()
        await DictionaryTerm(
            term="Baz",
            definition="Baz is a qux.",
            company_id=company.id,
        ).insert()
        global_term = await DictionaryTerm(
            term="Bar",
            definition="Bar is a baz.",
            is_global=True,
        ).insert()
        await DictionaryTerm(
            term="Qux",
            definition="Qux is a quux.",
            is_global=True,
        ).insert()
        await DictionaryTerm(
            term="Baz",
            definition="Baz is a qux.",
            company_id=PydanticObjectId(),
        ).insert()

        # When we list all dictionary terms
        count, dictionary_terms = await DictionaryService().list_all_dictionary_terms(
            company=company, limit=10, offset=0, term="bar"
        )
        # Then we should get the correct count and dictionary terms
        assert count == 2
        assert dictionary_terms == [global_term, company_term]

    async def test_list_all_dictionary_terms_skip_and_limit(
        self, company_factory: Callable[[], Company], debug: Callable[[Any], None]
    ) -> None:
        """Test the list_all_dictionary_terms method."""
        await DictionaryTerm.delete_all()
        company = await company_factory()
        company_term_1 = await DictionaryTerm(
            term="Foo",
            definition="Foo is a bar.",
            company_id=company.id,
            synonyms=["Bar"],
        ).insert()
        company_term_2 = await DictionaryTerm(
            term="Baz",
            definition="Baz is a qux.",
            company_id=company.id,
            is_global=True,
        ).insert()
        await DictionaryTerm(
            term="Bar",
            definition="Bar is a baz.",
            is_global=True,
        ).insert()
        await DictionaryTerm(
            term="Qux",
            definition="Qux is a quux.",
            is_global=True,
        ).insert()
        await DictionaryTerm(
            term="Qux",
            definition="Qux is a quux.",
            company_id=company.id,
            is_archived=True,
        ).insert()

        # When we list all dictionary terms
        count, dictionary_terms = await DictionaryService().list_all_dictionary_terms(
            company=company, limit=2, offset=1
        )
        # Then we should get the correct count and dictionary terms
        assert count == 4
        assert dictionary_terms == [company_term_2, company_term_1]
