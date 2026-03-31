"""Character schemas."""

from typing import Annotated

from beanie import PydanticObjectId
from litestar.plugins.pydantic import PydanticDTO
from pydantic import BaseModel, Field, field_serializer

from vapi.constants import HunterEdgeType
from vapi.db.models import Trait
from vapi.db.models.character import Character
from vapi.lib.dto import COMMON_EXCLUDES, dto_config
from vapi.utils.models import create_model_without_fields


class CharacterPatchDTO(PydanticDTO[Character]):
    """Character patch DTO."""

    config = dto_config(
        exclude={
            "id",
            "date_created",
            "date_modified",
            "company_id",
            "campaign_id",
            "user_creator_id",
            "concept_name",
            "traits",
            "character_trait_ids",
            "name",
            "name_full",
            "vampire_attributes.clan_name",
            "werewolf_attributes.tribe_name",
            "werewolf_attributes.auspice_name",
            "hunter_attributes.edges",
            "specialties",
            "is_chargen",
            "starting_points",
            "asset_ids",
            "date_killed",
        },
        partial=True,
        max_nested_depth=2,
    )


class CharacterResponseDTO(PydanticDTO[Character]):
    """Character response DTO."""

    config = dto_config(exclude={"is_chargen"})


class CharacterTraitCreate(BaseModel):
    """Character trait create DTO."""

    trait_id: Annotated[PydanticObjectId | None, Field(examples=["68c1f7152cae3787a09a74fa"])]
    value: Annotated[int, Field(ge=0, le=100)] = 0


# Dynamically create a new Character model to use for post requests
CreateCharacterDTO = create_model_without_fields(
    base_model=Character,
    new_name="CreateCharacterDTO",
    exclude={
        "id",
        "archive_date",
        "campaign_id",
        "character_trait_ids",
        "company_id",
        "concept_name",
        "date_created",
        "date_killed",
        "date_modified",
        "is_archived",
        "is_chargen",
        "model_version",
        "name",
        "name_full",
        "revision_id",
        "specialties",
        "status",
        "traits",
        "user_creator_id",
        "user_player_id",
        "starting_points",
        "asset_ids",
    },
    nested_excludes={
        "vampire_attributes": {"clan_name"},
        "werewolf_attributes": {"tribe_name", "auspice_name", "total_renown"},
        "mage_attributes": {"sphere", "tradition"},
    },
    add_fields={
        "traits": (
            list[CharacterTraitCreate] | None,
            Field(description="The traits to create for the character.", default_factory=list),
        ),  # type: ignore[dict-item]
        "user_player_id": (
            PydanticObjectId | None,
            Field(
                examples=["68c1f7152cae3787a09a74fa"],
                description="The ID of the user playing this character. If not provided, the current user will be used.",
                default=None,
            ),
        ),  # type: ignore[dict-item]
    },
)

########### FULL SHEET DTOs ###########


class FullSheetCharacterTraitDTO(BaseModel):
    """A Character Trait on the full sheet."""

    id: PydanticObjectId
    value: int
    trait: Trait
    character_id: PydanticObjectId

    @field_serializer("trait")
    def serialize_trait(self, trait: Trait) -> dict:
        """Serialize the trait."""
        return trait.model_dump(mode="json", exclude=COMMON_EXCLUDES)


class FullSheetTraitSubcategoryDTO(BaseModel):
    """A Trait Subcategory on the full sheet."""

    id: PydanticObjectId
    name: str
    description: str | None = None
    initial_cost: int
    upgrade_cost: int
    show_when_empty: bool
    requires_parent: bool
    pool: str | None = None
    system: str | None = None
    hunter_edge_type: HunterEdgeType | None = None
    character_traits: list[FullSheetCharacterTraitDTO]
    available_traits: list[Trait] = []

    @field_serializer("available_traits")
    def serialize_available_traits(self, traits: list[Trait]) -> list[dict]:
        """Serialize available traits."""
        return [t.model_dump(mode="json", exclude=COMMON_EXCLUDES) for t in traits]


class FullSheetTraitCategoryDTO(BaseModel):
    """A Trait Category on the full sheet."""

    id: PydanticObjectId
    name: str
    description: str | None = None
    initial_cost: int
    upgrade_cost: int
    show_when_empty: bool
    order: int

    subcategories: list[FullSheetTraitSubcategoryDTO]
    character_traits: list[FullSheetCharacterTraitDTO]
    available_traits: list[Trait] = []

    @field_serializer("available_traits")
    def serialize_available_traits(self, traits: list[Trait]) -> list[dict]:
        """Serialize available traits."""
        return [t.model_dump(mode="json", exclude=COMMON_EXCLUDES) for t in traits]


class FullSheetTraitSectionDTO(BaseModel):
    """A Trait Section on the full sheet."""

    id: PydanticObjectId
    name: str
    description: str | None = None
    order: int
    show_when_empty: bool
    categories: list[FullSheetTraitCategoryDTO]


class CharacterFullSheetDTO(BaseModel):
    """A Character Full Sheet."""

    sections: list[FullSheetTraitSectionDTO]
    character: Character

    @field_serializer("character")
    def serialize_character(self, character: Character) -> dict:
        """Serialize the character."""
        return character.model_dump(
            mode="json",
            exclude=COMMON_EXCLUDES | {"character_trait_ids", "is_chargen"},
        )


# Rebuild models so that forward references (Trait, HunterEdgeType) from
# TYPE_CHECKING imports are resolved at runtime when this module is fully loaded.
from vapi.constants import HunterEdgeType  # noqa: E402
from vapi.db.models import Trait  # noqa: E402

_rebuild_ns = {"Trait": Trait, "HunterEdgeType": HunterEdgeType}
FullSheetCharacterTraitDTO.model_rebuild(_types_namespace=_rebuild_ns)
FullSheetTraitSubcategoryDTO.model_rebuild(_types_namespace=_rebuild_ns)
FullSheetTraitCategoryDTO.model_rebuild(_types_namespace=_rebuild_ns)
FullSheetTraitSectionDTO.model_rebuild(_types_namespace=_rebuild_ns)
CharacterFullSheetDTO.model_rebuild(_types_namespace=_rebuild_ns)
