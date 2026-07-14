"""Unit tests for powers on dictionary term responses."""

import pytest

from vapi.constants import DictionarySourceType
from vapi.db.sql_models.character_sheet import Trait
from vapi.domain.controllers.dictionary.dto import DictionaryTermResponse
from vapi.domain.services.dictionary_svc import DictionaryService

pytestmark = pytest.mark.anyio


async def test_dictionary_term_from_model_includes_passed_powers(
    trait_factory, trait_power_factory, dictionary_term_factory
):
    """Verify from_model embeds powers supplied for a trait-sourced term."""
    # Given a trait with a power and a term sourced from it
    trait = await trait_factory(name="Biothaumaturgy")
    power = await trait_power_factory(trait=trait, level=1, name="Thaumaturgical Forensics")
    term = await dictionary_term_factory(
        term="biothaumaturgy",
        definition="d",
        source_type=DictionarySourceType.TRAIT,
        source_id=trait.id,
    )

    # When the response is built with the resolved powers
    response = DictionaryTermResponse.from_model(term, powers=[power])

    # Then the power is present
    assert [p.name for p in response.powers] == ["Thaumaturgical Forensics"]


async def test_dictionary_term_from_model_defaults_to_empty_powers(dictionary_term_factory):
    """Verify a non-trait term returns an empty powers list."""
    # Given a plain company term with no source
    term = await dictionary_term_factory(term="house rule", definition="d")

    # When the response is built with no powers
    response = DictionaryTermResponse.from_model(term)

    # Then powers is empty
    assert response.powers == []


async def test_powers_by_source_id_groups_trait_terms(
    trait_factory, trait_power_factory, dictionary_term_factory
):
    """Verify the resolver batch-loads powers keyed by trait source id and ignores non-trait terms."""
    # Given a trait term with powers and a non-trait term
    trait = await trait_factory(name="Biothaumaturgy")
    await trait_power_factory(trait=trait, level=1, name="First")
    await trait_power_factory(trait=trait, level=2, name="Second")
    trait_term = await dictionary_term_factory(
        term="biothaumaturgy",
        definition="d",
        source_type=DictionarySourceType.TRAIT,
        source_id=trait.id,
    )
    plain_term = await dictionary_term_factory(term="house rule", definition="d")

    # When powers are resolved for both terms
    result = await DictionaryService().powers_by_source_id([trait_term, plain_term])

    # Then only the trait's id maps to its ordered powers
    # trait_factory returns a uuid_utils.UUID; refetch to get the stdlib uuid.UUID
    # that DB-sourced power.trait_id uses, since the two do not hash-equal.
    trait = await Trait.get(id=trait.id)
    assert [p.name for p in result[trait.id]] == ["First", "Second"]
    # The non-trait term contributes no entry, so the trait is the only key.
    assert list(result.keys()) == [trait.id]
