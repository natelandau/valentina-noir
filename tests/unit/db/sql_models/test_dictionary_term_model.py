"""Test DictionaryTerm model validation."""

from collections.abc import Callable
from uuid import uuid4

import pytest
from tortoise.exceptions import ValidationError

from vapi.constants import DictionarySourceType
from vapi.db.sql_models.dictionary import DictionaryTerm


class TestSourceFieldValidation:
    """Test source_type and source_id cross-field validation."""

    @pytest.mark.anyio
    async def test_save_source_type_without_source_id(
        self, dictionary_term_factory: Callable[..., DictionaryTerm]
    ) -> None:
        """Verify saving with source_type but no source_id raises ValidationError."""
        # Given / When / Then
        with pytest.raises(ValidationError, match="source_type and source_id must both be set"):
            await dictionary_term_factory(source_type=DictionarySourceType.TRAIT, source_id=None)

    @pytest.mark.anyio
    async def test_save_source_id_without_source_type(
        self, dictionary_term_factory: Callable[..., DictionaryTerm]
    ) -> None:
        """Verify saving with source_id but no source_type raises ValidationError."""
        # Given / When / Then
        with pytest.raises(ValidationError, match="source_type and source_id must both be set"):
            await dictionary_term_factory(source_type=None, source_id=uuid4())

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
