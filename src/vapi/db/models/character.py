"""Character model."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Annotated, ClassVar
from uuid import UUID  # noqa: TC003

from beanie import (
    Delete,
    Document,
    Insert,
    Link,
    PydanticObjectId,
    Replace,
    Save,
    SaveChanges,
    Update,
    after_event,
    before_event,
)
from pydantic import BeforeValidator, Field, computed_field

from vapi.constants import (
    CharacterClass,
    CharacterStatus,
    CharacterType,
    GameVersion,
    InventoryItemType,
)
from vapi.db.models.base import BaseDocument
from vapi.db.models.constants.trait import Trait  # noqa: TC001
from vapi.db.models.shared import Specialty  # noqa: TC001
from vapi.lib.validation import empty_string_to_none

from .base import HashedBaseModel, NameDescriptionSubDocument


class CharacterTrait(Document):
    """Character trait model."""

    character_id: PydanticObjectId
    trait: Link[Trait]
    value: int

    @after_event(Insert, Replace, Save, Update, SaveChanges)
    async def sync_to_character(self) -> None:
        """Add the character trait id to the character."""
        character = await Character.get(self.character_id)
        if character:
            if self.id not in character.character_trait_ids:
                character.character_trait_ids.append(self.id)
            await character.save()

    @before_event(Delete)
    async def remove_from_character(self) -> None:
        """Remove the character trait id from the character."""
        character = await Character.get(self.character_id)
        if character:
            if self.id in character.character_trait_ids:
                character.character_trait_ids.remove(self.id)
            await character.save()

    class Settings:
        """Settings for the CharacterTrait model."""

        indexes: ClassVar[list[str]] = ["character_id"]


class VampireAttributes(HashedBaseModel):
    """Vampire-specific attributes."""

    clan_id: Annotated[
        PydanticObjectId | None, Field(examples=["68c1f7152cae3787a09a74fa"], default=None)
    ] = None
    clan_name: Annotated[str | None, Field(default=None)] = None
    generation: Annotated[int | None, Field(default=None)] = None
    sire: Annotated[
        str | None,
        Field(min_length=3, max_length=50, default=None),
        BeforeValidator(empty_string_to_none),
    ] = None
    bane: Annotated[NameDescriptionSubDocument | None, Field(default=None)] = None
    compulsion: Annotated[NameDescriptionSubDocument | None, Field(default=None)] = None


class MageAttributes(HashedBaseModel):
    """Mage-specific attributes."""

    sphere: Annotated[
        str | None,
        Field(min_length=3, max_length=50, default=None),
        BeforeValidator(empty_string_to_none),
    ] = None
    tradition: Annotated[
        str | None,
        Field(min_length=3, max_length=50, default=None),
        BeforeValidator(empty_string_to_none),
    ] = None


class HunterAttributesEdgeModel(HashedBaseModel):
    """Hunter edge and perk model."""

    edge_id: PydanticObjectId
    perk_ids: list[PydanticObjectId] = Field(default_factory=list)


class HunterAttributes(HashedBaseModel):
    """Hunter-specific attributes."""

    creed: Annotated[
        str | None,
        Field(min_length=3, max_length=50, default=None),
        BeforeValidator(empty_string_to_none),
    ] = None
    edges: list[HunterAttributesEdgeModel] = Field(default_factory=list)


class WerewolfAttributes(HashedBaseModel):
    """Werewolf-specific attributes."""

    pack_name: Annotated[
        str | None,
        Field(min_length=3, max_length=50, default=None),
        BeforeValidator(empty_string_to_none),
    ] = None

    tribe_id: Annotated[PydanticObjectId | None, Field(examples=["68c1f7152cae3787a09a74fa"])] = (
        None
    )

    tribe_name: Annotated[str | None, Field(default=None)] = None
    auspice_id: Annotated[PydanticObjectId | None, Field(examples=["68c1f7152cae3787a09a74fa"])] = (
        None
    )
    auspice_name: Annotated[str | None, Field(default=None)] = None
    gift_ids: list[PydanticObjectId] = Field(default_factory=list)
    rite_ids: list[PydanticObjectId] = Field(default_factory=list)
    total_renown: int = 0


class CharacterInventory(BaseDocument):
    """Character inventory model."""

    character_id: PydanticObjectId
    name: str
    description: str | None = None
    type: InventoryItemType

    class Settings:
        """Settings for the CharacterInventory model."""

        indexes: ClassVar[list[str]] = ["character_id"]


class Character(BaseDocument):
    """Character model."""

    # Excluded from api responses, used for internal tracking
    is_temporary: bool = False
    is_chargen: bool = False
    chargen_session_id: UUID | None = None

    # Set programmatically
    date_killed: datetime | None = None

    # Character attributes
    character_class: CharacterClass
    type: Annotated[
        CharacterType,
        Field(
            examples=[CharacterType.PLAYER, CharacterType.NPC, CharacterType.STORYTELLER],
            default=CharacterType.PLAYER,
        ),
    ]
    game_version: GameVersion
    starting_points: int = 0
    asset_ids: list[PydanticObjectId] = Field(default_factory=list)

    name_first: Annotated[str, Field(min_length=3, default=None)]
    name_last: Annotated[str, Field(min_length=3, default=None)]
    name_nick: Annotated[
        str | None,
        Field(min_length=3, max_length=50, default=None),
        BeforeValidator(empty_string_to_none),
    ] = None

    age: int | None = None
    biography: Annotated[
        str | None,
        Field(min_length=3, default=None),
        BeforeValidator(empty_string_to_none),
    ] = None

    demeanor: Annotated[
        str | None,
        Field(
            min_length=3, max_length=50, examples=["Friendly", "Hostile", "Neutral"], default=None
        ),
        BeforeValidator(empty_string_to_none),
    ] = None
    nature: Annotated[
        str | None,
        Field(
            min_length=3, max_length=50, examples=["Warrior", "Professor", "Mobster"], default=None
        ),
        BeforeValidator(empty_string_to_none),
    ] = None

    concept_id: Annotated[PydanticObjectId | None, Field(examples=["68c1f7152cae3787a09a74fa"])] = (
        None
    )

    specialties: list[Specialty] = Field(default_factory=list)

    status: CharacterStatus = CharacterStatus.ALIVE

    user_creator_id: Annotated[PydanticObjectId, Field(examples=["68c1f7152cae3787a09a74fa"])]
    user_player_id: Annotated[PydanticObjectId, Field(examples=["68c1f7152cae3787a09a74fa"])]

    company_id: Annotated[PydanticObjectId, Field(examples=["68c1f7152cae3787a09a74fa"])]
    campaign_id: Annotated[PydanticObjectId, Field(examples=["68c1f7152cae3787a09a74fa"])]

    character_trait_ids: list[PydanticObjectId] = Field(default_factory=list)

    vampire_attributes: VampireAttributes = VampireAttributes()
    werewolf_attributes: WerewolfAttributes = WerewolfAttributes()
    mage_attributes: MageAttributes | None = None
    hunter_attributes: HunterAttributes | None = None

    @computed_field  # type: ignore [prop-decorator]
    @property
    def name(self) -> str:
        """Return the character's name."""
        return f"{self.name_first} {self.name_last}"

    @computed_field  # type: ignore [prop-decorator]
    @property
    def name_full(self) -> str:
        """Return the character's full name."""
        nick = f" '{self.name_nick}'" if self.name_nick else ""
        last = f" {self.name_last}" if self.name_last else ""

        return f"{self.name_first}{nick}{last}".strip()

    @before_event(Delete)
    async def delete_character_traits(self) -> None:
        """Delete the character traits before the character is deleted."""
        await CharacterTrait.find(CharacterTrait.character_id == self.id).delete()

    class Settings:
        """Settings for the Character model."""

        indexes: ClassVar[list[str]] = [
            "user_creator_id",
            "user_player_id",
            "company_id",
            "status",
            "campaign_id",
        ]
