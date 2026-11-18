"""Bound request integers, pagination offsets, and dictionary fields at decode time.

Out-of-range values must fail msgspec decoding (a 400 with a readable message) instead of
reaching an int4 column and surfacing as a database error.
"""

from typing import Any
from uuid import uuid4

import msgspec
import pytest

from vapi.asgi import create_app
from vapi.constants import (
    MAX_CHARACTER_AGE,
    MAX_DICTIONARY_SYNONYMS,
    MAX_EXTRA_HEALTH_LEVELS,
    MAX_PAGINATION_OFFSET,
    MAX_TRAIT_VALUE,
    MAX_URL_LENGTH,
    MAX_VAMPIRE_GENERATION,
    MIN_VAMPIRE_GENERATION,
)
from vapi.domain.controllers.character.dto import (
    CharacterCreate,
    CharacterPatch,
    CharacterTraitCreate,
    VampireAttributesCreate,
    VampireAttributesPatch,
)
from vapi.domain.controllers.character_health.dto import HealthStateSet
from vapi.domain.controllers.character_trait.dto import (
    CharacterTraitAddConstant,
    TraitModifyRequest,
)
from vapi.domain.controllers.dictionary.dto import DictionaryTermCreate, DictionaryTermPatch

INT4_OVERFLOW = 2_147_483_648

_CHARACTER_CREATE_BASE: dict[str, Any] = {
    "name_first": "Alice",
    "name_last": "Smith",
    "character_class": "VAMPIRE",
    "game_version": "V5",
    "campaign_id": str(uuid4()),
}


def _decode(struct: type[msgspec.Struct], payload: dict[str, Any]) -> msgspec.Struct:
    return msgspec.json.decode(msgspec.json.encode(payload), type=struct)


@pytest.mark.parametrize(
    ("struct", "payload"),
    [
        (CharacterCreate, _CHARACTER_CREATE_BASE | {"age": MAX_CHARACTER_AGE + 1}),
        (CharacterCreate, _CHARACTER_CREATE_BASE | {"age": INT4_OVERFLOW}),
        (CharacterPatch, {"age": MAX_CHARACTER_AGE + 1}),
        (VampireAttributesCreate, {"clan_id": str(uuid4()), "generation": INT4_OVERFLOW}),
        (
            VampireAttributesCreate,
            {"clan_id": str(uuid4()), "generation": MAX_VAMPIRE_GENERATION + 1},
        ),
        (
            VampireAttributesCreate,
            {"clan_id": str(uuid4()), "generation": MIN_VAMPIRE_GENERATION - 1},
        ),
        (VampireAttributesPatch, {"generation": MAX_VAMPIRE_GENERATION + 1}),
        (CharacterTraitCreate, {"trait_id": str(uuid4()), "value": INT4_OVERFLOW}),
        (CharacterTraitCreate, {"trait_id": str(uuid4()), "value": -1}),
        (CharacterTraitAddConstant, {"trait_id": str(uuid4()), "value": MAX_TRAIT_VALUE + 1}),
        (CharacterTraitAddConstant, {"trait_id": str(uuid4()), "value": -1}),
        (TraitModifyRequest, {"target_value": INT4_OVERFLOW, "currency": "NO_COST"}),
        (TraitModifyRequest, {"target_value": -1, "currency": "NO_COST"}),
        (HealthStateSet, {"extra_levels": MAX_EXTRA_HEALTH_LEVELS + 1}),
        (HealthStateSet, {"extra_levels": INT4_OVERFLOW}),
    ],
)
def test_out_of_range_integers_fail_decoding(
    struct: type[msgspec.Struct], payload: dict[str, Any]
) -> None:
    """Verify integers outside the game range are rejected before reaching the database."""
    # When / Then
    with pytest.raises(msgspec.ValidationError):
        _decode(struct, payload)


@pytest.mark.parametrize(
    ("struct", "payload"),
    [
        (CharacterCreate, _CHARACTER_CREATE_BASE | {"age": MAX_CHARACTER_AGE}),
        (CharacterPatch, {"age": 0}),
        (
            VampireAttributesCreate,
            {"clan_id": str(uuid4()), "generation": MIN_VAMPIRE_GENERATION},
        ),
        (VampireAttributesPatch, {"generation": MAX_VAMPIRE_GENERATION}),
        (VampireAttributesPatch, {"generation": None}),
        (CharacterTraitCreate, {"trait_id": str(uuid4()), "value": MAX_TRAIT_VALUE}),
        (CharacterTraitAddConstant, {"trait_id": str(uuid4()), "value": 0}),
        (TraitModifyRequest, {"target_value": MAX_TRAIT_VALUE, "currency": "NO_COST"}),
        (HealthStateSet, {"extra_levels": MAX_EXTRA_HEALTH_LEVELS}),
    ],
)
def test_in_range_integers_decode(struct: type[msgspec.Struct], payload: dict[str, Any]) -> None:
    """Verify boundary values inside the game range still decode."""
    # When / Then
    _decode(struct, payload)


def test_list_endpoints_bound_offset() -> None:
    """Verify every route's `offset` query parameter has the shared upper bound."""
    # Given every route handler that takes an offset
    app = create_app()
    offsets = [
        (handler, handler.parsed_fn_signature.parameters["offset"])
        for route in app.routes
        for handler in getattr(route, "route_handlers", [])
        if "offset" in handler.parsed_fn_signature.parameters
    ]

    # Then each one caps the offset
    unbounded = [
        str(handler)
        for handler, param in offsets
        if param.kwarg_definition is None
        or param.kwarg_definition.le != MAX_PAGINATION_OFFSET
        or param.kwarg_definition.ge != 0
    ]
    assert offsets
    assert unbounded == []


@pytest.mark.parametrize("struct", [DictionaryTermCreate, DictionaryTermPatch])
@pytest.mark.parametrize(
    "link",
    [
        "javascript:alert(1)",
        "ftp://example.com/file",
        "data:text/html,hello",
        "example.com",
        "https://example.com\n",
        "https://example.com/a b",
        "https://" + "a" * MAX_URL_LENGTH,
    ],
)
def test_dictionary_link_rejects_non_http_urls(struct: type[msgspec.Struct], link: str) -> None:
    """Verify dictionary links accept only bounded http and https URLs."""
    # When / Then
    with pytest.raises(msgspec.ValidationError):
        _decode(struct, {"term": "Kindred", "link": link})


@pytest.mark.parametrize("struct", [DictionaryTermCreate, DictionaryTermPatch])
@pytest.mark.parametrize("link", ["https://example.com/a?b=c", "HTTP://example.com", None])
def test_dictionary_link_accepts_http_urls(struct: type[msgspec.Struct], link: str | None) -> None:
    """Verify http, https, and null links decode."""
    # When
    term = _decode(struct, {"term": "Kindred", "link": link})

    # Then
    assert term.link == link  # ty:ignore[missing-attribute]


@pytest.mark.parametrize("struct", [DictionaryTermCreate, DictionaryTermPatch])
@pytest.mark.parametrize(
    "synonyms",
    [
        ["x"] * (MAX_DICTIONARY_SYNONYMS + 1),
        ["a" * 51],
        [""],
        ["   "],
    ],
)
def test_dictionary_synonyms_are_bounded(struct: type[msgspec.Struct], synonyms: list[str]) -> None:
    """Verify synonyms cap the item count and each item's length, and reject empty items."""
    # When / Then
    with pytest.raises(msgspec.ValidationError):
        _decode(struct, {"term": "Kindred", "synonyms": synonyms})
