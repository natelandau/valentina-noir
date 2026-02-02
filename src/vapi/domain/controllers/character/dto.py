"""Character schemas."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId
from litestar.plugins.pydantic import PydanticDTO
from pydantic import BaseModel, Field

from vapi.db.models.character import Character
from vapi.lib.dto import dto_config
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
            "traits",
            "name",
            "name_full",
            "vampire_attributes.clan_name",
            "werewolf_attributes.tribe_name",
            "werewolf_attributes.auspice_name",
            "hunter_attributes.edges",
            "specialties",
            "chargen_session_id",
            "is_chargen",
            "is_temporary",
            "starting_points",
            "asset_ids",
            "date_killed",
        },
        partial=True,
        max_nested_depth=2,
    )


class CharacterResponseDTO(PydanticDTO[Character]):
    """Character response DTO."""

    config = dto_config(exclude={"chargen_session_id", "is_chargen", "is_temporary"})


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
        "date_created",
        "date_killed",
        "date_modified",
        "is_archived",
        "is_chargen",
        "is_temporary",
        "model_version",
        "name",
        "name_full",
        "revision_id",
        "specialties",
        "status",
        "traits",
        "user_creator_id",
        "user_player_id",
        "chargen_session_id",
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
