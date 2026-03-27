"""Unit tests for dictionary services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from beanie import PydanticObjectId

from vapi.constants import DictionarySourceType
from vapi.db.models import Company, DictionaryTerm
from vapi.domain.services import DictionaryService
from vapi.lib.exceptions import ValidationError

if TYPE_CHECKING:
    from collections.abc import Callable

pytestmark = pytest.mark.anyio


class TestDictionaryService:
    """Test the dictionary service."""

    def test_verify_term_is_editable_false(self) -> None:
        """Test the verify_term_is_editable method."""
        dictionary_term = DictionaryTerm(
            term="Foo",
            definition="Foo is a bar.",
            source_type="trait",
            source_id=PydanticObjectId(),
        )
        with pytest.raises(
            ValidationError,
            match=r"You may not update dictionary terms that are not owned by your company",
        ):
            DictionaryService().verify_term_is_editable(
                dictionary_term, company_id=PydanticObjectId()
            )

    def test_verify_term_is_editable_false_not_company(self) -> None:
        """Test the verify_term_is_editable method."""
        dictionary_term = DictionaryTerm(
            term="Foo", definition="Foo is a bar.", company_id=PydanticObjectId()
        )
        with pytest.raises(
            ValidationError,
            match=r"You may not update dictionary terms that are not owned by your company",
        ):
            DictionaryService().verify_term_is_editable(
                dictionary_term, company_id=PydanticObjectId()
            )

    def test_verify_term_is_editable_false_no_company_id(self) -> None:
        """Verify term with no company_id is not editable."""
        # Given a term with no company_id and no source_type
        dictionary_term = DictionaryTerm(term="Foo", definition="Foo is a bar.")
        # When we verify editability, Then it should raise
        with pytest.raises(
            ValidationError,
            match=r"You may not update dictionary terms that are not owned by your company",
        ):
            DictionaryService().verify_term_is_editable(
                dictionary_term, company_id=PydanticObjectId()
            )

    def test_verify_term_is_editable_true(self) -> None:
        """Test the verify_term_is_editable method."""
        company_id = PydanticObjectId()
        dictionary_term = DictionaryTerm(
            term="Foo",
            definition="Foo is a bar.",
            source_type=None,
            company_id=company_id,
        )
        assert DictionaryService().verify_term_is_editable(dictionary_term, company_id)

    async def test_list_all_dictionary_terms(
        self,
        company_factory: Callable[[], Company],
        debug: Callable[[Any], None],
        dictionary_term_factory: Callable[..., DictionaryTerm],
    ) -> None:
        """Test the list_all_dictionary_terms method."""
        await DictionaryTerm.delete_all()
        company = await company_factory()
        company_term = await dictionary_term_factory(
            term="Foo",
            definition="Foo is a bar.",
            company_id=company.id,
        )
        global_term = await dictionary_term_factory(
            term="Bar",
            definition="Bar is a baz.",
            source_type=DictionarySourceType.TRAIT,
            source_id=PydanticObjectId(),
        )
        global_term.company_id = None
        await global_term.save()
        non_company_term = await dictionary_term_factory(
            term="Baz",
            definition="Baz is a qux.",
            company_id=PydanticObjectId(),
        )
        archived_term = await dictionary_term_factory(
            term="Qux",
            definition="Qux is a quux.",
            company_id=company.id,
            is_archived=True,
        )

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
        self,
        company_factory: Callable[[], Company],
        debug: Callable[[Any], None],
        dictionary_term_factory: Callable[..., DictionaryTerm],
    ) -> None:
        """Test the list_all_dictionary_terms method."""
        await DictionaryTerm.delete_all()
        company = await company_factory()
        company_term = await dictionary_term_factory(
            term="Foo",
            definition="Foo is a bar.",
            company_id=company.id,
            synonyms=["Bar"],
        )
        await dictionary_term_factory(
            term="Baz",
            definition="Baz is a qux.",
            company_id=company.id,
        )
        global_term = await dictionary_term_factory(
            term="Bar",
            definition="Bar is a baz.",
            source_type=DictionarySourceType.TRAIT,
            source_id=PydanticObjectId(),
        )
        await dictionary_term_factory(
            term="Qux",
            definition="Qux is a quux.",
            source_type=DictionarySourceType.TRAIT,
            source_id=PydanticObjectId(),
        )
        await dictionary_term_factory(
            term="Baz",
            definition="Baz is a qux.",
            company_id=PydanticObjectId(),
        )

        # When we list all dictionary terms
        count, dictionary_terms = await DictionaryService().list_all_dictionary_terms(
            company=company, limit=10, offset=0, term="bar"
        )
        # Then we should get the correct count and dictionary terms
        assert dictionary_terms == [global_term, company_term]
        assert count == 2

    async def test_list_all_dictionary_terms_skip_and_limit(
        self,
        company_factory: Callable[[], Company],
        debug: Callable[[Any], None],
        dictionary_term_factory: Callable[..., DictionaryTerm],
    ) -> None:
        """Test the list_all_dictionary_terms method."""
        await DictionaryTerm.delete_all()
        company = await company_factory()
        company_term_1 = await dictionary_term_factory(
            term="Foo",
            definition="Foo is a bar.",
            company_id=company.id,
            synonyms=["Bar"],
        )
        company_term_2 = await dictionary_term_factory(
            term="Baz",
            definition="Baz is a qux.",
            company_id=company.id,
            source_type=DictionarySourceType.TRAIT,
            source_id=PydanticObjectId(),
        )
        await dictionary_term_factory(
            term="Bar",
            definition="Bar is a baz.",
            source_type=DictionarySourceType.TRAIT,
            source_id=PydanticObjectId(),
        )
        await dictionary_term_factory(
            term="Qux",
            definition="Qux is a quux.",
            source_type=DictionarySourceType.TRAIT,
            source_id=PydanticObjectId(),
        )
        await dictionary_term_factory(
            term="Qux",
            definition="Qux is a quux.",
            company_id=company.id,
            is_archived=True,
        )

        # When we list all dictionary terms
        count, dictionary_terms = await DictionaryService().list_all_dictionary_terms(
            company=company, limit=2, offset=1
        )
        # Then we should get the correct count and dictionary terms
        assert count == 4
        assert dictionary_terms == [company_term_2, company_term_1]
