"""Integration tests for the dictionary term sync service."""

from __future__ import annotations

from uuid import uuid4

import pytest

from vapi.cli.lib.dictionary import DictionaryService
from vapi.constants import DictionarySourceType
from vapi.db.sql_models.dictionary import DictionaryTerm

pytestmark = pytest.mark.anyio


class TestDictionaryUpsert:
    """Integration tests for DictionaryService._upsert_term scoping."""

    async def test_upsert_term_ignores_null_source_type_collision(
        self, dictionary_term_factory
    ) -> None:
        """Verify the seed upsert leaves a same-named global term that has no source_type untouched."""
        # Given: a pre-existing global term with NULL source_type sharing a normalized name
        orphan = await dictionary_term_factory(
            term="collision-term", definition="original", link=None
        )
        service = DictionaryService()
        service._existing_terms = {}  # empty cache forces the cache-miss DB fallback path
        seed_source_id = uuid4()

        # When: seeding a term with the same name but a real source_type
        try:
            await service._upsert_term(
                "collision-term",
                definition="seeded",
                source_type=DictionarySourceType.TRAIT,
                source_id=seed_source_id,
            )

            # Then: the NULL-source term is unchanged and a separate seed term now exists
            await orphan.refresh_from_db()
            assert orphan.definition == "original"
            assert orphan.source_type is None

            seeded = await DictionaryTerm.filter(
                term="collision-term", source_type=DictionarySourceType.TRAIT
            ).first()
            assert seeded is not None
            assert seeded.id != orphan.id
        finally:
            # dictionary_term is a preserved table, so remove the seed row this test created
            await DictionaryTerm.filter(
                term="collision-term", source_type=DictionarySourceType.TRAIT
            ).delete()
