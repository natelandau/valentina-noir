"""Pydantic Model utilities."""

import types
from typing import Any, Union, get_args, get_origin

from pydantic import BaseModel, Field, create_model
from pydantic.fields import FieldInfo


def create_model_without_fields(
    base_model: type[BaseModel],
    exclude: set[str],
    new_name: str,
    nested_excludes: dict[str, set[str]] | None = None,
    add_fields: dict[str, tuple[type, Any]] | None = None,
) -> type[BaseModel]:
    """Create a new Pydantic model excluding specified fields and optionally adding new ones.

    Args:
        base_model: The original model class
        exclude: Set of field names to exclude from the base model
        new_name: Name for the new model class
        nested_excludes: Dict mapping field names to sets of fields to exclude from nested models
                        e.g., {'address': {'internal_id'}, 'contacts': {'phone'}}
        add_fields: Dict mapping new field names to (type, default) tuples
                   e.g., {'new_field': (str, ...), 'optional_field': (int | None, None)}
    """
    nested_excludes = nested_excludes or {}
    add_fields = add_fields or {}
    fields = {}

    for name, field_info in base_model.model_fields.items():
        if name in exclude:
            continue

        annotation = field_info.annotation

        # Check if this field has nested exclusions
        if name in nested_excludes:
            new_annotation = _process_nested_type(
                annotation, nested_excludes[name], f"{new_name}_{name.capitalize()}"
            )
            if new_annotation is not None:
                annotation = new_annotation
                # Update the default if it was a model instance
                if isinstance(field_info.default, BaseModel):
                    # Convert to the new model type
                    default_data = field_info.default.model_dump(exclude=nested_excludes[name])
                    new_default = new_annotation(**default_data)
                    # Reconstruct Field with the new default
                    default = Field(
                        default=new_default,
                        description=field_info.description,
                        examples=field_info.examples,
                        title=field_info.title,
                        **_extract_field_metadata(field_info),
                    )
                else:
                    default = _reconstruct_field(field_info)
            else:
                default = _reconstruct_field(field_info)
        else:
            default = _reconstruct_field(field_info)

        fields[name] = (annotation, default)

    # Add new fields
    fields.update(
        {
            field_name: (field_type, field_default)
            for field_name, (field_type, field_default) in add_fields.items()
        }
    )

    return create_model(new_name, **fields)  # type: ignore[call-overload]


def _reconstruct_field(field_info: FieldInfo) -> Any:
    """Reconstruct a Field with all its metadata preserved."""
    default_value = ... if field_info.is_required() else field_info.default

    # Build Field kwargs
    field_kwargs = {
        "default": default_value,
        "description": field_info.description,
        "examples": field_info.examples,
        "title": field_info.title,
        **_extract_field_metadata(field_info),
    }

    # Remove None values to avoid overriding Pydantic defaults, but preserve 'default' since None is a valid default value
    field_kwargs = {k: v for k, v in field_kwargs.items() if v is not None or k == "default"}

    # Handle default_factory separately
    if hasattr(field_info, "default_factory") and field_info.default_factory is not None:
        field_kwargs.pop("default", None)
        field_kwargs["default_factory"] = field_info.default_factory

    return Field(**field_kwargs)


def _extract_field_metadata(field_info: FieldInfo) -> dict:  # noqa: C901
    """Extract validation metadata from FieldInfo."""
    metadata = {}

    # Numeric constraints
    if hasattr(field_info, "ge") and field_info.ge is not None:
        metadata["ge"] = field_info.ge
    if hasattr(field_info, "gt") and field_info.gt is not None:
        metadata["gt"] = field_info.gt
    if hasattr(field_info, "le") and field_info.le is not None:
        metadata["le"] = field_info.le
    if hasattr(field_info, "lt") and field_info.lt is not None:
        metadata["lt"] = field_info.lt
    if hasattr(field_info, "multiple_of") and field_info.multiple_of is not None:
        metadata["multiple_of"] = field_info.multiple_of

    # String constraints
    if hasattr(field_info, "min_length") and field_info.min_length is not None:
        metadata["min_length"] = field_info.min_length
    if hasattr(field_info, "max_length") and field_info.max_length is not None:
        metadata["max_length"] = field_info.max_length
    if hasattr(field_info, "pattern") and field_info.pattern is not None:
        metadata["pattern"] = field_info.pattern

    # Other constraints
    if hasattr(field_info, "discriminator") and field_info.discriminator is not None:
        metadata["discriminator"] = field_info.discriminator
    if hasattr(field_info, "alias") and field_info.alias is not None:
        metadata["alias"] = field_info.alias
    if hasattr(field_info, "deprecated") and field_info.deprecated is not None:
        metadata["deprecated"] = field_info.deprecated

    return metadata


def _process_nested_type(annotation: Any, exclude: set[str], model_name: str) -> Any:
    """Process a type annotation to create modified nested models."""
    origin = get_origin(annotation)

    # Handle Optional (Union with None)
    if origin is Union or origin is types.UnionType:
        args = get_args(annotation)
        # Filter out None and process the rest
        non_none_args = [arg for arg in args if arg is not type(None)]

        if len(non_none_args) == 1:
            processed = _process_nested_type(non_none_args[0], exclude, model_name)
            if processed is not None:
                # Reconstruct Optional with the processed type using | syntax
                return processed | None
        return None

    # Handle list
    if origin is list:
        args = get_args(annotation)
        if args:
            inner_type = args[0]
            processed = _process_nested_type(inner_type, exclude, model_name)
            if processed is not None:
                # Reconstruct list type
                return list[processed]  # type: ignore[valid-type]
        return None

    # Handle direct BaseModel
    if hasattr(annotation, "model_fields"):
        return create_model_without_fields(annotation, exclude, model_name)

    return None
