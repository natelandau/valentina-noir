"""Test DictionaryTerm model validation."""

from collections.abc import Callable
from uuid import UUID, uuid4

import pytest
from tortoise.exceptions import ValidationError

from vapi.constants import DictionarySourceType
from vapi.db.sql_models.dictionary import DictionaryTerm


class TestSourceFieldValidation:
    """Test source_type and source_id cross-field validation."""

    @pytest.mark.anyio
    @pytest.mark.parametrize(
        ("source_type", "source_id"),
        [
            (DictionarySourceType.TRAIT, None),
            (None, uuid4()),
        ],
        ids=["source_type-without-source_id", "source_id-without-source_type"],
    )
    async def test_save_partial_source_fields_raises(
        self,
        dictionary_term_factory: Callable[..., DictionaryTerm],
        source_type: DictionarySourceType | None,
        source_id: UUID | None,
    ) -> None:
        """Verify saving with only one of source_type or source_id raises ValidationError."""
        # Given / When / Then
        with pytest.raises(ValidationError, match="source_type and source_id must both be set"):
            await dictionary_term_factory(source_type=source_type, source_id=source_id)

    @pytest.mark.anyio
    async def test_save_both_source_fields_set(
        self, dictionary_term_factory: Callable[..., DictionaryTerm]
    ) -> None:
        """Verify saving with both source_type and source_id succeeds."""
        # Given / When
        term = await dictionary_term_factory(
            source_type=DictionarySourceType.TRAIT, source_id=uuid4()
        )

        # Then
        assert term.source_type == DictionarySourceType.TRAIT
        assert term.source_id is not None

    @pytest.mark.anyio
    async def test_save_both_source_fields_null(
        self, dictionary_term_factory: Callable[..., DictionaryTerm]
    ) -> None:
        """Verify saving with both source_type and source_id null succeeds."""
        # Given / When
        term = await dictionary_term_factory(source_type=None, source_id=None)

        # Then
        assert term.source_type is None
        assert term.source_id is None
