"""Tests for translating msgspec validation messages."""

import enum
import logging
import uuid
from datetime import datetime
from typing import Annotated

import msgspec
import pytest

from vapi.lib.validation_messages import (
    body_path_from_cause,
    enum_values_for,
    resolve_field,
    translate_message,
)


class _Color(enum.Enum):
    RED = "red"


class _Bounded(msgspec.Struct):
    n: Annotated[int, msgspec.Meta(le=100)]


class _Text(msgspec.Struct):
    s: Annotated[str, msgspec.Meta(max_length=3)]


class _Items(msgspec.Struct):
    a: Annotated[list[int], msgspec.Meta(max_length=2)]


class _Mapping(msgspec.Struct):
    d: Annotated[dict[str, int], msgspec.Meta(max_length=1)]


class _OptText(msgspec.Struct):
    s: str | None


class _Num(msgspec.Struct):
    n: int


class _Id(msgspec.Struct):
    i: uuid.UUID


class _Pick(msgspec.Struct):
    c: _Color


class _When(msgspec.Struct):
    d: datetime


class _Pattern(msgspec.Struct):
    s: Annotated[str, msgspec.Meta(pattern="^a+$")]


class _Req(msgspec.Struct):
    name: str


class _Strict(msgspec.Struct, forbid_unknown_fields=True):
    name: str = ""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Expected `int` <= 100", "Must be at most 100."),
        ("Expected `float` <= 2.5", "Must be at most 2.5."),
        ("Expected `int` >= 1", "Must be at least 1."),
        ("Expected `int` < 10", "Must be less than 10."),
        ("Expected `int` > 0", "Must be greater than 0."),
        ("Expected `str` of length <= 50", "Must be at most 50 characters."),
        ("Expected `str` of length >= 3", "Must be at least 3 characters."),
        ("Expected `str` of length <= 1", "Must be at most 1 character."),
        ("Expected `str` of length >= 1", "Must be at least 1 character."),
        ("Expected `array` of length <= 1", "Must have at most 1 item."),
        ("Expected `int | str`, got `float`", "Is not valid."),
        ("Expected `array` of length <= 20", "Must have at most 20 items."),
        ("Expected `array` of length >= 1", "Must have at least 1 item."),
        ("Expected `object` of length <= 5", "Must have at most 5 items."),
        ("Expected `int`, got `str`", "Must be a whole number."),
        ("Expected `int | null`, got `str`", "Must be a whole number."),
        ("Expected `float`, got `str`", "Must be a number."),
        ("Expected `str`, got `int`", "Must be text."),
        ("Expected `str | null`, got `int`", "Must be text."),
        ("Expected `bool`, got `str`", "Must be true or false."),
        ("Expected `array`, got `str`", "Must be a list."),
        ("Expected `object`, got `str`", "Must be an object."),
        ("Expected `uuid | null`, got `int`", "Must be a valid ID."),
        ("Invalid UUID", "Must be a valid ID."),
        ("Expected `datetime`, got `int`", "Must be a valid date and time."),
        ("Invalid RFC3339 encoded datetime", "Must be a valid date and time."),
        ("Invalid RFC3339 encoded date", "Must be a valid date."),
        ("Invalid RFC3339 encoded time", "Must be a valid time."),
        ("Expected `str` matching regex '^a+$'", "Is not in the expected format."),
        ("Expected `int`, got `null`", "Must have a value."),
        ("Invalid enum value 'z'", "Is not an allowed value."),
        ("Invalid enum value 7", "Is not an allowed value."),
        ("Object missing required field `name`", "This field is required."),
        ("Object contains unknown field `zz`", "Is not a recognized field."),
        ("Something msgspec says one day", "Is not valid."),
    ],
)
def test_translates_message(raw: str, expected: str) -> None:
    """Verify each known msgspec message maps to its sentence."""
    assert translate_message(raw) == expected


def test_enum_message_lists_allowed_values() -> None:
    """Verify an enum failure lists the allowed values when supplied."""
    assert translate_message("Invalid enum value 'z'", enum_values=["a", "b"]) == (
        "Must be one of: a, b."
    )


def test_unmatched_message_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Verify an unmatched message is logged at INFO."""
    with caplog.at_level(logging.INFO):
        translate_message("Something msgspec says one day")

    assert any(
        r.levelno == logging.INFO and "Something msgspec says one day" in str(r.error)
        for r in caplog.records
        if hasattr(r, "error")
    )


def test_enum_values_are_coerced_to_text() -> None:
    """Verify non-string allowed values are joined as text."""
    assert translate_message("Invalid enum value 7", enum_values=[1, 2]) == "Must be one of: 1, 2."


def test_field_name_patterns() -> None:
    """Verify missing and unknown field messages yield the field name."""
    assert resolve_field(path="", raw="Object missing required field `name`") == "name"
    assert resolve_field(path="", raw="Object contains unknown field `zz`") == "zz"


def _raw(typ: type, data: object) -> str:
    """Return the msgspec message for converting `data` to `typ`, without its path suffix."""
    with pytest.raises(msgspec.ValidationError) as info:
        msgspec.convert(data, typ, strict=True)
    return str(info.value).split(" - at ")[0]


@pytest.mark.parametrize(
    ("typ", "data", "expected"),
    [
        (_Bounded, {"n": 101}, "Must be at most 100."),
        (_Text, {"s": "abcd"}, "Must be at most 3 characters."),
        (_Items, {"a": [1, 2, 3]}, "Must have at most 2 items."),
        (_Mapping, {"d": {"a": 1, "b": 2}}, "Must have at most 1 item."),
        (_Num, {"n": "x"}, "Must be a whole number."),
        (_OptText, {"s": 5}, "Must be text."),
        (_Id, {"i": "nope"}, "Must be a valid ID."),
        (_Pick, {"c": "z"}, "Is not an allowed value."),
        (_When, {"d": "nope"}, "Must be a valid date and time."),
        (_Pattern, {"s": "bbb"}, "Is not in the expected format."),
        (int, None, "Must have a value."),
        (_Req, {}, "This field is required."),
        (_Strict, {"zz": 1}, "Is not a recognized field."),
    ],
)
def test_pins_msgspec_wording(typ: type, data: object, expected: str) -> None:
    """Verify real msgspec output still maps, so an upgrade that changes wording fails here."""
    assert translate_message(_raw(typ, data)) == expected


@pytest.mark.parametrize(
    ("typ", "data"),
    [
        (_Pick, {"c": "secret-value-123"}),
        (_Id, {"i": "secret-value-123"}),
        (_Pattern, {"s": "secret-value-123"}),
    ],
)
def test_never_echoes_value(typ: type, data: object) -> None:
    """Verify the rejected value never appears in the message."""
    raw = _raw(typ, data)

    if typ is _Pick:
        # Proves the suppression is real: msgspec itself echoes enum values.
        assert "secret-value-123" in raw
    assert "secret-value-123" not in translate_message(raw)


class _Kind(enum.Enum):
    A = "a"
    B = "b"
    C = "c"


class _Named(msgspec.Struct):
    name: str


class _Inner(msgspec.Struct):
    x: int


class _WithMeta(msgspec.Struct):
    metadata: _Inner | None = None


class _Item(msgspec.Struct):
    trait_id: int


class _KindStruct(msgspec.Struct):
    kind: _Kind | msgspec.UnsetType = msgspec.UNSET


class _StrKind(msgspec.Struct):
    kind: str | _Kind = "a"


def _cause(typ: object, payload: object) -> msgspec.ValidationError:
    wrapper = msgspec.defstruct("_Wrap", [("data", typ)])
    with pytest.raises(msgspec.ValidationError) as exc_info:
        msgspec.convert({"data": payload}, wrapper)
    return exc_info.value


def _path_and_field(typ: object, payload: object) -> tuple[str, str]:
    parsed = body_path_from_cause(_cause(typ, payload))
    assert parsed is not None
    raw, path = parsed
    return path, resolve_field(path=path, raw=raw)


def test_body_path_root_missing_field() -> None:
    """Verify a missing root field yields an empty path and the field name."""
    parsed = body_path_from_cause(_cause(_Named, {}))
    assert parsed == ("Object missing required field `name`", "")
    assert resolve_field(path="", raw=parsed[0]) == "name"


def test_body_path_nested_mangled_parent() -> None:
    """Verify a parent name ending in data is kept intact."""
    assert _path_and_field(_WithMeta, {"metadata": {"x": "s"}})[0] == "metadata.x"


def test_body_path_nested_missing_field() -> None:
    """Verify a nested missing field resolves to the dotted path."""
    assert _path_and_field(_WithMeta, {"metadata": {}})[1] == "metadata.x"


def test_body_path_list_body() -> None:
    """Verify a top-level list body gives an indexed path."""
    assert _path_and_field(list[_Item], [{"trait_id": "s"}]) == ("[0].trait_id", "[0].trait_id")
    assert _path_and_field(list[_Item], [{}])[1] == "[0].trait_id"


def test_body_path_none_without_data_prefix() -> None:
    """Verify non-body errors and missing causes return None."""

    class _Q(msgspec.Struct):
        kind: _Kind

    with pytest.raises(msgspec.ValidationError) as exc_info:
        msgspec.convert({"kind": "z"}, _Q)
    assert body_path_from_cause(exc_info.value) is None
    assert body_path_from_cause(None) is None


def test_body_path_none_for_root_name_starting_with_data() -> None:
    """Verify a root field such as `database` is not mistaken for the body."""

    class _Db(msgspec.Struct):
        database: int

    with pytest.raises(msgspec.ValidationError) as exc_info:
        msgspec.convert({"database": "x"}, _Db)
    assert body_path_from_cause(exc_info.value) is None


def test_resolve_field_unknown_field() -> None:
    """Verify an unknown field is appended to its parent path."""
    raw = "Object contains unknown field `zz`"
    assert resolve_field(path="metadata", raw=raw) == "metadata.zz"


def test_enum_values_for_struct_field() -> None:
    """Verify enum values come back in declaration order."""
    assert enum_values_for("kind", _KindStruct) == ["a", "b", "c"]


def test_enum_values_for_list_item() -> None:
    """Verify list indexes are followed."""
    assert enum_values_for("[1].kind", list[_KindStruct]) == ["a", "b", "c"]


def test_enum_values_none_for_str_union_or_unknown_path() -> None:
    """Verify ambiguous unions and unresolved paths give None."""
    assert enum_values_for("kind", _StrKind) is None
    assert enum_values_for("nope", _KindStruct) is None


def test_enum_values_none_inside_dict() -> None:
    """Verify dict values are not walked."""

    class _D(msgspec.Struct):
        d: dict[str, _Kind]

    assert enum_values_for("d[k]", _D) is None
    assert enum_values_for("d", _D) is None


def test_enum_values_for_annotated_enum() -> None:
    """Verify metadata wrappers are unwrapped."""

    class _A(msgspec.Struct):
        kind: Annotated[_Kind, msgspec.Meta(description="x")] | msgspec.UnsetType = msgspec.UNSET

    assert enum_values_for("kind", _A) == ["a", "b", "c"]
