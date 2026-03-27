"""Test dictionary model."""

from __future__ import annotations

import pytest
from beanie import PydanticObjectId

from vapi.constants import DictionarySourceType
from vapi.db.models import DictionaryTerm
from vapi.lib.exceptions import ValidationError

pytestmark = pytest.mark.anyio


async def test_dictionary_term_to_lowercase() -> None:
    """Verify term and synonyms are lowercased on insert."""
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
    """Verify validation rejects terms without definition or link."""
    with pytest.raises(ValidationError, match=r"Must have either a definition or a link."):
        await DictionaryTerm(
            term="Foo",
            synonyms=["Qux", "Bar", "BAR"],
        ).insert()


@pytest.mark.parametrize(
    ("source_type", "source_id"),
    [
        (DictionarySourceType.TRAIT, None),
        (None, PydanticObjectId()),
    ],
    ids=["source_type_without_source_id", "source_id_without_source_type"],
)
def test_source_fields_must_be_coupled(
    source_type: DictionarySourceType | None, source_id: PydanticObjectId | None
) -> None:
    """Verify validation rejects terms with only one of source_type or source_id set."""
    with pytest.raises(
        ValueError, match=r"source_type and source_id must both be set or both be None"
    ):
        DictionaryTerm(
            term="Foo",
            definition="Foo is a bar.",
            source_type=source_type,
            source_id=source_id,
        )


@pytest.mark.parametrize(
    ("source_type", "source_id"),
    [
        (DictionarySourceType.CLAN, PydanticObjectId()),
        (None, None),
    ],
    ids=["both_set", "both_none"],
)
def test_source_fields_coupled_valid(
    source_type: DictionarySourceType | None, source_id: PydanticObjectId | None
) -> None:
    """Verify validation accepts terms with both or neither source fields set."""
    term = DictionaryTerm(
        term="Foo",
        definition="Foo is a bar.",
        source_type=source_type,
        source_id=source_id,
    )
    assert term.source_type == source_type
    assert term.source_id == source_id
