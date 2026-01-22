"""Test dictionary model."""

from __future__ import annotations

import pytest

from vapi.db.models import DictionaryTerm
from vapi.lib.exceptions import ValidationError

pytestmark = pytest.mark.anyio


async def test_dictionary_term_to_lowercase() -> None:
    """Test the dictionary term to lowercase."""
    term = await DictionaryTerm(
        term="Foo",
        synonyms=["Qux", "Bar", "BAR"],
        definition="Foo is a bar.",
    ).insert()

    assert term.term == "foo"
    assert term.synonyms == ["bar", "qux"]
    assert term.definition == "Foo is a bar."

    await term.delete()


async def test_dictionary_term_must_have_definition_or_link() -> None:
    """Test the dictionary term must have a definition or a link."""
    with pytest.raises(ValidationError, match=r"Must have either a definition or a link."):
        await DictionaryTerm(
            term="Foo",
            synonyms=["Qux", "Bar", "BAR"],
        ).insert()
