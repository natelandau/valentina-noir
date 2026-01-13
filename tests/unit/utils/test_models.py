"""Test the models utility module."""

from __future__ import annotations

import pytest
from pydantic import BaseModel, Field
from pydantic_core import PydanticUndefined

from vapi.utils.models import (
    _extract_field_metadata,
    _process_nested_type,
    _reconstruct_field,
    create_model_without_fields,
)

pytestmark = pytest.mark.anyio


class SimpleModel(BaseModel):
    """Simple test model."""

    name: str
    age: int
    email: str | None = None


class NestedModel(BaseModel):
    """Nested model for testing."""

    street: str
    city: str
    internal_id: int = 0


class ParentModel(BaseModel):
    """Parent model with nested model."""

    name: str
    address: NestedModel
    tags: list[str] = Field(default_factory=list)


class ModelWithConstraints(BaseModel):
    """Model with field constraints for testing metadata extraction."""

    name: str = Field(min_length=3, max_length=50)
    age: int = Field(ge=0, le=150)
    score: float = Field(gt=0.0, lt=100.0)
    count: int = Field(multiple_of=5)


class ModelWithOptionalNested(BaseModel):
    """Model with optional nested model."""

    name: str
    address: NestedModel | None = None


class ModelWithListNested(BaseModel):
    """Model with list of nested models."""

    name: str
    addresses: list[NestedModel] = Field(default_factory=list)


class TestCreateModelWithoutFields:
    """Tests for the create_model_without_fields function."""

    @pytest.mark.no_clean_db
    def test_exclude_single_field(self) -> None:
        """Verify excluding a single field from a model."""
        # Given: A simple model and a field to exclude
        exclude = {"email"}

        # When: Creating a new model without the field
        new_model = create_model_without_fields(SimpleModel, exclude, "SimpleModelNoEmail")

        # Then: New model should not have the excluded field
        assert "name" in new_model.model_fields
        assert "age" in new_model.model_fields
        assert "email" not in new_model.model_fields

    @pytest.mark.no_clean_db
    def test_exclude_multiple_fields(self) -> None:
        """Verify excluding multiple fields from a model."""
        # Given: A simple model and multiple fields to exclude
        exclude = {"age", "email"}

        # When: Creating a new model without the fields
        new_model = create_model_without_fields(SimpleModel, exclude, "SimpleModelMinimal")

        # Then: New model should only have name field
        assert "name" in new_model.model_fields
        assert "age" not in new_model.model_fields
        assert "email" not in new_model.model_fields

    @pytest.mark.no_clean_db
    def test_model_name_is_set(self) -> None:
        """Verify the new model has the specified name."""
        # Given: A model and a new name
        new_name = "CustomModelName"

        # When: Creating a new model
        new_model = create_model_without_fields(SimpleModel, set(), new_name)

        # Then: Model should have the specified name
        assert new_model.__name__ == new_name

    @pytest.mark.no_clean_db
    def test_add_new_fields(self) -> None:
        """Verify adding new fields to the model."""
        # Given: A model and new fields to add
        add_fields = {
            "new_required": (str, ...),
            "new_optional": (int | None, None),
            "new_default": (str, "default_value"),
        }

        # When: Creating a new model with added fields
        new_model = create_model_without_fields(
            SimpleModel, set(), "SimpleModelExtended", add_fields=add_fields
        )

        # Then: New model should have all original and new fields
        assert "name" in new_model.model_fields
        assert "new_required" in new_model.model_fields
        assert "new_optional" in new_model.model_fields
        assert "new_default" in new_model.model_fields

    @pytest.mark.no_clean_db
    def test_exclude_and_add_fields(self) -> None:
        """Verify excluding and adding fields simultaneously."""
        # Given: Fields to exclude and add
        exclude = {"email"}
        add_fields = {"phone": (str | None, None)}

        # When: Creating a new model
        new_model = create_model_without_fields(
            SimpleModel, exclude, "SimpleModelModified", add_fields=add_fields
        )

        # Then: Model should have correct fields
        assert "email" not in new_model.model_fields
        assert "phone" in new_model.model_fields

    @pytest.mark.no_clean_db
    def test_nested_model_exclusion(self) -> None:
        """Verify excluding fields from nested models."""
        # Given: Nested exclusions
        nested_excludes = {"address": {"internal_id"}}

        # When: Creating a new model with nested exclusions
        new_model = create_model_without_fields(
            ParentModel, set(), "ParentModelClean", nested_excludes=nested_excludes
        )

        # Then: Nested model should not have internal_id
        address_annotation = new_model.model_fields["address"].annotation
        assert "street" in address_annotation.model_fields
        assert "city" in address_annotation.model_fields
        assert "internal_id" not in address_annotation.model_fields

    @pytest.mark.no_clean_db
    def test_model_can_be_instantiated(self) -> None:
        """Verify the created model can be instantiated."""
        # Given: A new model
        new_model = create_model_without_fields(SimpleModel, {"email"}, "InstantiableModel")

        # When: Creating an instance
        instance = new_model(name="Test", age=25)

        # Then: Instance should have correct values
        assert instance.name == "Test"
        assert instance.age == 25

    @pytest.mark.no_clean_db
    def test_preserves_required_fields(self) -> None:
        """Verify required fields remain required in new model."""
        # Given: A model with required fields
        # When: Creating a new model
        new_model = create_model_without_fields(SimpleModel, {"email"}, "RequiredFieldsModel")

        # Then: name and age should still be required
        assert new_model.model_fields["name"].is_required()
        assert new_model.model_fields["age"].is_required()

    @pytest.mark.no_clean_db
    def test_preserves_optional_fields(self) -> None:
        """Verify optional fields remain optional in new model."""
        # Given: A model with optional field
        # When: Creating a new model without excluding email
        new_model = create_model_without_fields(SimpleModel, set(), "OptionalFieldsModel")

        # Then: email should still be optional
        assert not new_model.model_fields["email"].is_required()


class TestReconstructField:
    """Tests for the _reconstruct_field function."""

    @pytest.mark.no_clean_db
    def test_preserves_required_field(self) -> None:
        """Verify required field remains required."""
        # Given: A required field info
        field_info = SimpleModel.model_fields["name"]

        # When: Reconstructing the field
        new_field = _reconstruct_field(field_info)

        # Then: Field should be required (default is PydanticUndefined or ...)
        assert new_field.default is PydanticUndefined or new_field.default is ...

    @pytest.mark.no_clean_db
    def test_preserves_optional_field_default(self) -> None:
        """Verify optional field preserves default value."""
        # Given: An optional field info
        field_info = SimpleModel.model_fields["email"]

        # When: Reconstructing the field
        new_field = _reconstruct_field(field_info)

        # Then: Field should have None as default
        assert new_field.default is None

    @pytest.mark.no_clean_db
    def test_preserves_description(self) -> None:
        """Verify field description is preserved."""

        # Given: A model with description
        class ModelWithDesc(BaseModel):
            name: str = Field(description="The user's name")

        field_info = ModelWithDesc.model_fields["name"]

        # When: Reconstructing the field
        new_field = _reconstruct_field(field_info)

        # Then: Description should be preserved
        assert new_field.description == "The user's name"

    @pytest.mark.no_clean_db
    def test_preserves_default_factory(self) -> None:
        """Verify default_factory is preserved."""
        # Given: A field with default_factory
        field_info = ParentModel.model_fields["tags"]

        # When: Reconstructing the field
        new_field = _reconstruct_field(field_info)

        # Then: default_factory should be preserved
        assert new_field.default_factory is not None

    @pytest.mark.no_clean_db
    def test_preserves_examples(self) -> None:
        """Verify field examples are preserved."""

        # Given: A model with examples
        class ModelWithExamples(BaseModel):
            name: str = Field(examples=["John", "Jane"])

        field_info = ModelWithExamples.model_fields["name"]

        # When: Reconstructing the field
        new_field = _reconstruct_field(field_info)

        # Then: Examples should be preserved
        assert new_field.examples == ["John", "Jane"]


class TestExtractFieldMetadata:
    """Tests for the _extract_field_metadata function."""

    @pytest.mark.no_clean_db
    def test_extracts_alias(self) -> None:
        """Verify alias is extracted."""

        # Given: A model with alias
        class ModelWithAlias(BaseModel):
            user_name: str = Field(alias="userName")

        field_info = ModelWithAlias.model_fields["user_name"]

        # When: Extracting metadata
        metadata = _extract_field_metadata(field_info)

        # Then: alias should be in metadata
        assert metadata["alias"] == "userName"

    @pytest.mark.no_clean_db
    def test_extracts_deprecated(self) -> None:
        """Verify deprecated flag is extracted."""

        # Given: A model with deprecated field
        class ModelWithDeprecated(BaseModel):
            old_field: str = Field(deprecated=True)

        field_info = ModelWithDeprecated.model_fields["old_field"]

        # When: Extracting metadata
        metadata = _extract_field_metadata(field_info)

        # Then: deprecated should be in metadata
        assert metadata["deprecated"] is True

    @pytest.mark.no_clean_db
    def test_returns_empty_dict_for_no_metadata(self) -> None:
        """Verify empty dict returned for field without extractable metadata."""
        # Given: A field without alias or deprecated
        field_info = SimpleModel.model_fields["name"]

        # When: Extracting metadata
        metadata = _extract_field_metadata(field_info)

        # Then: Should not have alias or deprecated
        assert "alias" not in metadata
        assert "deprecated" not in metadata

    @pytest.mark.no_clean_db
    def test_returns_dict_type(self) -> None:
        """Verify function returns a dict."""
        # Given: Any field info
        field_info = SimpleModel.model_fields["name"]

        # When: Extracting metadata
        metadata = _extract_field_metadata(field_info)

        # Then: Should return a dict
        assert isinstance(metadata, dict)

    @pytest.mark.no_clean_db
    def test_pydantic_v2_constraints_in_metadata(self) -> None:
        """Verify Pydantic v2 stores constraints in metadata attribute."""
        # Given: A field with constraints - Pydantic v2 stores these in metadata
        field_info = ModelWithConstraints.model_fields["age"]

        # When: Checking the field
        # Then: Constraints should be in metadata attribute (not direct attributes)
        assert hasattr(field_info, "metadata")
        assert len(field_info.metadata) > 0


class TestProcessNestedType:
    """Tests for the _process_nested_type function."""

    @pytest.mark.no_clean_db
    def test_processes_direct_basemodel(self) -> None:
        """Verify direct BaseModel types are processed."""
        # Given: A nested model type and exclusions
        exclude = {"internal_id"}

        # When: Processing the type
        result = _process_nested_type(NestedModel, exclude, "ProcessedNested")

        # Then: Should return a new model without excluded field
        assert result is not None
        assert "street" in result.model_fields
        assert "internal_id" not in result.model_fields

    @pytest.mark.no_clean_db
    def test_processes_optional_basemodel(self) -> None:
        """Verify Optional[BaseModel] types are processed."""
        # Given: An optional nested model type
        annotation = ModelWithOptionalNested.model_fields["address"].annotation
        exclude = {"internal_id"}

        # When: Processing the type
        result = _process_nested_type(annotation, exclude, "ProcessedOptional")

        # Then: Should return Optional with processed model
        assert result is not None

    @pytest.mark.no_clean_db
    def test_processes_list_of_basemodel(self) -> None:
        """Verify list[BaseModel] types are processed."""
        # Given: A list of nested models type
        annotation = ModelWithListNested.model_fields["addresses"].annotation
        exclude = {"internal_id"}

        # When: Processing the type
        result = _process_nested_type(annotation, exclude, "ProcessedList")

        # Then: Should return list with processed model
        assert result is not None

    @pytest.mark.no_clean_db
    def test_returns_none_for_simple_types(self) -> None:
        """Verify None is returned for non-model types."""
        # Given: A simple type
        # When: Processing the type
        result = _process_nested_type(str, {"field"}, "ProcessedStr")

        # Then: Should return None
        assert result is None

    @pytest.mark.no_clean_db
    def test_returns_none_for_int(self) -> None:
        """Verify None is returned for int types."""
        # Given: An int type
        # When: Processing the type
        result = _process_nested_type(int, set(), "ProcessedInt")

        # Then: Should return None
        assert result is None


class TestEndToEnd:
    """End-to-end tests for model creation scenarios."""

    @pytest.mark.no_clean_db
    def test_complex_model_transformation(self) -> None:
        """Verify complex model with multiple transformations."""

        # Given: A complex model
        class ComplexModel(BaseModel):
            id: int
            name: str = Field(description="User name")
            email: str | None = None
            address: NestedModel | None = None
            tags: list[str] = Field(default_factory=list)

        # When: Creating a new model with exclusions and additions
        new_model = create_model_without_fields(
            ComplexModel,
            exclude={"id"},
            new_name="ComplexModelDTO",
            nested_excludes={"address": {"internal_id"}},
            add_fields={"external_ref": (str | None, None)},
        )

        # Then: All transformations should be applied
        assert "id" not in new_model.model_fields
        assert "name" in new_model.model_fields
        assert "external_ref" in new_model.model_fields

        # And: Description should be preserved
        name_field = new_model.model_fields["name"]
        assert name_field.description == "User name"

    @pytest.mark.no_clean_db
    def test_created_model_validates_types(self) -> None:
        """Verify created model validates types correctly."""
        # Given: A new model
        new_model = create_model_without_fields(SimpleModel, {"email"}, "ValidationModel")

        # When/Then: Valid data should work
        instance = new_model(name="John", age=25)
        assert instance.name == "John"

        # When/Then: Invalid type should raise
        with pytest.raises(ValueError, match="validation error"):
            new_model(name="John", age="not_an_int")

    @pytest.mark.no_clean_db
    def test_model_json_serialization(self) -> None:
        """Verify created model can serialize to JSON."""
        # Given: A new model instance
        new_model = create_model_without_fields(SimpleModel, {"email"}, "SerializableModel")
        instance = new_model(name="Test", age=30)

        # When: Serializing to JSON
        json_data = instance.model_dump_json()

        # Then: Should serialize correctly
        assert "Test" in json_data
        assert "30" in json_data
        assert "email" not in json_data

    @pytest.mark.no_clean_db
    def test_model_schema_generation(self) -> None:
        """Verify created model generates correct schema."""
        # Given: A new model
        new_model = create_model_without_fields(SimpleModel, {"email"}, "SchemaModel")

        # When: Getting JSON schema
        schema = new_model.model_json_schema()

        # Then: Schema should have correct properties
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]
        assert "email" not in schema["properties"]
