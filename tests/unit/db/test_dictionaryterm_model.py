"""Test dictionary."""

from __future__ import annotations

import pytest
from beanie import PydanticObjectId

from vapi.db.models import DictionaryTerm

pytestmark = pytest.mark.anyio


async def test_dictionary_terms_to_lowercase() -> None:
    """Test the dictionary term to lowercase."""
    dictionary_term = DictionaryTerm(
        term="Foo",
        synonyms=["Qux", "Bar", "BAR"],
        definition="  Foo is a bar.  ",
        company_id=PydanticObjectId(),
    )
    await dictionary_term.save()
    assert dictionary_term.term == "foo"
    assert dictionary_term.synonyms == ["bar", "qux"]
    assert dictionary_term.definition == "Foo is a bar."
