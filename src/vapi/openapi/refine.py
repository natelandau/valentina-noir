"""Fill gaps in the OpenAPI schema that Litestar generates from msgspec Structs.

Litestar's schema plugins cannot target bare unions (their registry needs a named type), so
these fixes run once on the built schema at startup, before it is first served.
"""

import dataclasses
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, get_args

import msgspec
from litestar.openapi.spec import Discriminator, OpenAPIType, Reference, Schema

from vapi.domain.controllers.character_trait.dto import TrackerResponse

if TYPE_CHECKING:
    from litestar import Litestar
    from litestar.openapi.spec import OpenAPI

_COMPONENT_PREFIX = "#/components/schemas/"

# Unions of tagged Structs that get a `discriminator` wherever they appear.
TAGGED_UNIONS: tuple[Any, ...] = (TrackerResponse,)

# msgspec numeric constraint to OpenAPI keyword.
_NUMERIC_CONSTRAINTS = (
    ("ge", "minimum"),
    ("le", "maximum"),
    ("gt", "exclusive_minimum"),
    ("lt", "exclusive_maximum"),
)


def _iter_schemas(node: object) -> Iterator[Schema]:
    """Yield every `Schema` nested anywhere in an OpenAPI spec object."""
    if isinstance(node, Schema):
        yield node
    if isinstance(node, dict):
        for value in node.values():
            yield from _iter_schemas(value)
    elif isinstance(node, list | tuple):
        for value in node:
            yield from _iter_schemas(value)
    elif dataclasses.is_dataclass(node) and not isinstance(node, type):
        for field in dataclasses.fields(node):
            yield from _iter_schemas(getattr(node, field.name))


def _discriminator_for(union: Any) -> tuple[frozenset[str], Discriminator]:
    """Return the component refs of a tagged union and the discriminator that maps to them."""
    members: tuple[type[msgspec.Struct], ...] = get_args(union)
    tag_field = members[0].__struct_config__.tag_field
    mapping = {
        str(member.__struct_config__.tag): f"{_COMPONENT_PREFIX}{member.__name__}"
        for member in members
    }
    return frozenset(mapping.values()), Discriminator(property_name=str(tag_field), mapping=mapping)


def _is_null(schema: Schema | Reference) -> bool:
    return isinstance(schema, Schema) and schema.type == OpenAPIType.NULL


def add_discriminators(openapi: "OpenAPI") -> None:
    """Add a discriminator to every `oneOf` that lists exactly the members of a tagged union.

    A nullable union becomes `oneOf: [{oneOf: [...], discriminator}, {type: null}]` so the
    discriminator only covers object branches.
    """
    unions = [_discriminator_for(union) for union in TAGGED_UNIONS]
    for schema in list(_iter_schemas(openapi)):
        if not schema.one_of or schema.discriminator is not None:
            continue
        refs = [s for s in schema.one_of if isinstance(s, Reference)]
        others = [s for s in schema.one_of if not isinstance(s, Reference)]
        ref_names = frozenset(r.ref for r in refs)
        for members, discriminator in unions:
            if ref_names != members:
                continue
            if not others:
                schema.discriminator = discriminator
            elif all(_is_null(s) for s in others):
                schema.one_of = [Schema(one_of=refs, discriminator=discriminator), *others]
            break


def _vapi_structs() -> Iterator[type[msgspec.Struct]]:
    pending = list(msgspec.Struct.__subclasses__())
    while pending:
        cls = pending.pop()
        pending.extend(cls.__subclasses__())
        if cls.__module__.startswith("vapi."):
            yield cls


def _copy_numeric_constraints(*, prop: Schema, numeric: Any) -> None:
    """Set the msgspec bounds of `numeric` on the integer or number branch of `prop`."""
    for branch in prop.one_of or []:
        if not isinstance(branch, Schema) or branch.type not in (
            OpenAPIType.INTEGER,
            OpenAPIType.NUMBER,
        ):
            continue
        for constraint, keyword in _NUMERIC_CONSTRAINTS:
            value = getattr(numeric, constraint)
            if value is not None:
                setattr(branch, keyword, float(value))


def restore_optional_constraints(openapi: "OpenAPI") -> None:
    """Copy numeric constraints onto the non-null branch of optional Struct fields.

    Litestar renders `Annotated[int, Meta(ge=0)] | None` as `oneOf: [integer, null]` and drops
    the constraint; this puts `minimum` and the other bounds back.
    """
    components = openapi.components.schemas or {}
    for cls in _vapi_structs():
        component = components.get(cls.__name__)
        if component is None or component.title != cls.__name__ or not component.properties:
            continue
        info = msgspec.inspect.type_info(cls)
        if not isinstance(info, msgspec.inspect.StructType):
            continue
        for field in info.fields:
            if not isinstance(field.type, msgspec.inspect.UnionType):
                continue
            numeric = [
                t
                for t in field.type.types
                if isinstance(t, msgspec.inspect.IntType | msgspec.inspect.FloatType)
            ]
            prop = component.properties.get(field.encode_name)
            if len(numeric) == 1 and isinstance(prop, Schema):
                _copy_numeric_constraints(prop=prop, numeric=numeric[0])


async def refine_openapi_schema(app: "Litestar") -> None:
    """Apply the schema fixes to the app's cached OpenAPI schema on startup."""
    if app.openapi_config is None:
        return
    openapi = app.openapi_schema
    add_discriminators(openapi)
    restore_optional_constraints(openapi)
