"""Translate msgspec validation messages into short, readable sentences."""

import functools
import logging
import re
from collections.abc import Callable, Sequence
from typing import Any

import msgspec

logger = logging.getLogger(__name__)

_NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
_VALID_ID = "Must be a valid ID."
_VALID_DATETIME = "Must be a valid date and time."
_VALID_DATE = "Must be a valid date."
_VALID_TIME = "Must be a valid time."
_FALLBACK = "Is not valid."

_ENUM_RE = re.compile(r"^Invalid enum value")
_TYPE_ERROR_RE = re.compile(r"^Expected `([^`]+)`, got `[^`]+`$")
_FIELD_NAME_RE = re.compile(r"Object (?:missing required|contains unknown) field `([^`]+)`")
_CAUSE_RE = re.compile(r"^(?P<message>.*) - at `\$\.data(?P<rest>(?:[.\[][^`]*)?)`$", re.DOTALL)
_SEGMENT_RE = re.compile(r"\[(\d+)\]|([^.\[\]]+)")

_Handler = str | Callable[[re.Match[str], Sequence[object] | None], str]


def _length_sentence(match: re.Match[str], _enum_values: Sequence[object] | None) -> str:
    """Build the sentence for a length bound."""
    kind, operator, count = match.groups()
    bound = "at most" if operator == "<=" else "at least"
    plural = count != "1"
    if kind == "str":
        return f"Must be {bound} {count} {'characters' if plural else 'character'}."
    return f"Must have {bound} {count} {'items' if plural else 'item'}."


def _enum_sentence(_match: re.Match[str], enum_values: Sequence[object] | None) -> str:
    """List the allowed values when they are known."""
    if enum_values:
        return f"Must be one of: {', '.join(str(v) for v in enum_values)}."
    return "Is not an allowed value."


# Order matters: the first match wins, so the `null` rule precedes the type fallback. A
# template handler is formatted with the match groups; a callable builds the sentence.
_RULES: tuple[tuple[re.Pattern[str], _Handler], ...] = (
    (re.compile(r"^Expected `([^`]+)` of length ([<>]=) (\d+)$"), _length_sentence),
    (_ENUM_RE, _enum_sentence),
    (re.compile(r"^Expected `[^`]+`, got `null`$"), "Must have a value."),
    (re.compile(rf"^Expected `[^`]+` <= ({_NUMBER})$"), "Must be at most {0}."),
    (re.compile(rf"^Expected `[^`]+` >= ({_NUMBER})$"), "Must be at least {0}."),
    (re.compile(rf"^Expected `[^`]+` < ({_NUMBER})$"), "Must be less than {0}."),
    (re.compile(rf"^Expected `[^`]+` > ({_NUMBER})$"), "Must be greater than {0}."),
    (re.compile(r"^Expected `str` matching regex "), "Is not in the expected format."),
    (re.compile(r"^Invalid UUID"), _VALID_ID),
    (re.compile(r"^Invalid RFC3339 encoded datetime"), _VALID_DATETIME),
    (re.compile(r"^Invalid RFC3339 encoded date"), _VALID_DATE),
    (re.compile(r"^Invalid RFC3339 encoded time"), _VALID_TIME),
    (re.compile(r"Object missing required field `([^`]+)`"), "This field is required."),
    (re.compile(r"Object contains unknown field `([^`]+)`"), "Is not a recognized field."),
)

_TYPE_SENTENCES: dict[str, str] = {
    "int": "Must be a whole number.",
    "float": "Must be a number.",
    "str": "Must be text.",
    "bool": "Must be true or false.",
    "array": "Must be a list.",
    "object": "Must be an object.",
    "uuid": _VALID_ID,
    "datetime": _VALID_DATETIME,
    "date": _VALID_DATE,
    "time": _VALID_TIME,
}


def translate_message(raw: str, *, enum_values: Sequence[object] | None = None) -> str:
    """Translate a msgspec validation message into a short sentence.

    The result never contains the rejected value. An unmatched message is logged
    and replaced with a generic sentence.

    Args:
        raw: The msgspec message without its trailing " - at `$.path`" part.
        enum_values: Allowed values to list when `raw` is an enum failure.

    Returns:
        A short sentence ending with a period.
    """
    for pattern, handler in _RULES:
        match = pattern.search(raw)
        if match:
            if isinstance(handler, str):
                return handler.format(*match.groups())
            return handler(match, enum_values)

    type_match = _TYPE_ERROR_RE.match(raw)
    if type_match:
        types = [t for t in type_match.group(1).split(" | ") if t != "null"]
        sentence = _TYPE_SENTENCES.get(types[0]) if len(types) == 1 else None
        if sentence:
            return sentence

    logger.info("Untranslated validation message", extra={"error": raw, "component": "validation"})
    return _FALLBACK


def is_enum_message(raw: str) -> bool:
    """Report whether `raw` is an enum failure, so callers look up allowed values only then.

    Args:
        raw: The msgspec message without its location.

    Returns:
        True when `raw` reports a value outside an enum.
    """
    return _ENUM_RE.match(raw) is not None


def body_path_from_cause(cause: BaseException | None) -> tuple[str, str] | None:
    """Split a msgspec error on a request body into its message and field path.

    Parse the original error instead of Litestar's rewritten key, because that
    rewrite strips "data." from inside names such as `metadata.x`.

    Args:
        cause: The exception Litestar chained to its validation error.

    Returns:
        The message and the path below `$.data` (empty for the root), or None
        when the error is not on the request body.
    """
    if cause is None:
        return None
    match = _CAUSE_RE.match(str(cause))
    if not match:
        return None
    return match.group("message"), match.group("rest").removeprefix(".")


def resolve_field(*, path: str, raw: str) -> str:
    """Return the client-facing field name for a body error.

    A missing or unknown field is reported at its parent, so append its name.

    Args:
        path: The path below `$.data`.
        raw: The msgspec message without its location.

    Returns:
        The dotted field path.
    """
    match = _FIELD_NAME_RE.search(raw)
    if not match:
        return path
    name = match.group(1)
    return f"{path}.{name}" if path else name


@functools.lru_cache(maxsize=256)
def cached_type_info(annotation: Any) -> msgspec.inspect.Type:
    """Return `msgspec.inspect.type_info` for `annotation`, cached because body types repeat.

    Args:
        annotation: A hashable type annotation.

    Returns:
        The msgspec type description.
    """
    return msgspec.inspect.type_info(annotation)


def unwrap_optional(info: msgspec.inspect.Type) -> msgspec.inspect.Type | None:
    """Reduce a type to its single meaningful member, stripping metadata and `null`.

    Args:
        info: A msgspec type description.

    Returns:
        The one non-null member, or None when a union has several.
    """
    while isinstance(info, msgspec.inspect.Metadata):
        info = info.type
    if not isinstance(info, msgspec.inspect.UnionType):
        return info
    # msgspec already drops `UnsetType` from unions, so only `null` remains to filter.
    members = [t for t in info.types if not isinstance(t, msgspec.inspect.NoneType)]
    if len(members) != 1:
        return None
    return unwrap_optional(members[0])


def enum_values_for(path: str, body_type: Any) -> list[str] | None:
    """List the allowed values of the enum at `path` in a request body type.

    Args:
        path: The path below `$.data`, such as `kind` or `[1].kind`.
        body_type: The annotated body type the request was decoded into.

    Returns:
        The enum member values as text, or None when the path does not end at
        an unambiguous enum.
    """
    try:
        info: msgspec.inspect.Type | None = cached_type_info(body_type)
    except TypeError:
        return None

    for index, name in _SEGMENT_RE.findall(path):
        info = unwrap_optional(info) if info else None
        if index and isinstance(info, msgspec.inspect.ListType):
            info = info.item_type
        elif name and isinstance(info, msgspec.inspect.StructType):
            info = next((f.type for f in info.fields if f.encode_name == name), None)
        else:
            return None

    if info is None:
        return None
    info = unwrap_optional(info)
    if isinstance(info, msgspec.inspect.EnumType):
        return [str(member.value) for member in info.cls]
    return None
