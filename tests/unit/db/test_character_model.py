"""Test Tortoise Character model properties."""

import pytest

from vapi.db.sql_models.character import Character


class TestCharacterModelProperties:
    """Test Character model computed properties."""

    @pytest.mark.anyio
    async def test_character_name(self, pg_character_factory, pg_company_factory) -> None:
        """Verify name property returns 'First Last'."""
        # Given a character
        company = await pg_company_factory()
        character = await pg_character_factory(name_first="John", name_last="Doe", company=company)

        # Then
        assert character.name == "John Doe"

    @pytest.mark.anyio
    async def test_character_name_full_without_nick(
        self, pg_character_factory, pg_company_factory
    ) -> None:
        """Verify name_full returns 'First Last' when no nickname."""
        # Given a character without a nickname
        company = await pg_company_factory()
        character = await pg_character_factory(
            name_first="John", name_last="Doe", name_nick=None, company=company
        )

        # Then
        assert character.name_full == "John Doe"

    @pytest.mark.anyio
    async def test_character_name_full_with_nick(
        self, pg_character_factory, pg_company_factory
    ) -> None:
        """Verify name_full returns "First 'Nick' Last" when nickname set."""
        # Given a character with a nickname
        company = await pg_company_factory()
        character = await pg_character_factory(
            name_first="John", name_last="Doe", name_nick="JD", company=company
        )

        # Then
        assert character.name_full == "John 'JD' Doe"

    @pytest.mark.anyio
    async def test_character_concept_name_with_concept(
        self, pg_character_factory, pg_character_concept_factory, pg_company_factory
    ) -> None:
        """Verify concept_name returns the concept's name when prefetched."""
        # Given a concept and a character with that concept
        concept = await pg_character_concept_factory(name="Scholar")
        company = await pg_company_factory()
        character = await pg_character_factory(concept=concept, company=company)

        # When we re-fetch with concept prefetched
        character = await Character.filter(id=character.id).prefetch_related("concept").first()

        # Then
        assert character.concept_name == "Scholar"

    @pytest.mark.anyio
    async def test_character_concept_name_without_concept(
        self, pg_character_factory, pg_company_factory
    ) -> None:
        """Verify concept_name returns None when no concept set."""
        # Given a character without a concept
        company = await pg_company_factory()
        character = await pg_character_factory(concept=None, company=company)

        # When we re-fetch with concept prefetched
        character = await Character.filter(id=character.id).prefetch_related("concept").first()

        # Then
        assert character.concept_name is None
