"""Character and related models: traits, inventory, attributes, specialties."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from tortoise import fields
from tortoise.validators import MinLengthValidator

from vapi.constants import (
    CharacterClass,
    CharacterStatus,
    CharacterType,
    GameVersion,
    InventoryItemType,
    SpecialtyType,
)
from vapi.db.sql_models.base import BaseModel

if TYPE_CHECKING:
    from vapi.db.sql_models.campaign import Campaign
    from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
    from vapi.db.sql_models.character_concept import CharacterConcept
    from vapi.db.sql_models.character_sheet import Trait
    from vapi.db.sql_models.chargen_session import ChargenSession
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.diceroll import DiceRoll
    from vapi.db.sql_models.notes import Note
    from vapi.db.sql_models.user import User


class Character(BaseModel):
    """A player or NPC character in a campaign."""

    name_first = fields.CharField(max_length=50, validators=[MinLengthValidator(3)])
    name_last = fields.CharField(max_length=50, validators=[MinLengthValidator(3)])
    name_nick = fields.CharField(max_length=50, null=True, validators=[MinLengthValidator(3)])
    character_class = fields.CharEnumField(CharacterClass)
    type = fields.CharEnumField(CharacterType)
    game_version = fields.CharEnumField(GameVersion)
    status = fields.CharEnumField(CharacterStatus, default=CharacterStatus.ALIVE)
    starting_points = fields.IntField(default=0)
    age = fields.IntField(null=True)
    biography = fields.TextField(null=True, validators=[MinLengthValidator(3)])
    demeanor = fields.CharField(max_length=50, null=True, validators=[MinLengthValidator(3)])
    nature = fields.CharField(max_length=50, null=True, validators=[MinLengthValidator(3)])
    is_temporary = fields.BooleanField(default=False)
    is_chargen = fields.BooleanField(default=False)
    date_killed = fields.DatetimeField(null=True)

    _empty_string_to_none_fields: ClassVar[frozenset[str]] = frozenset(
        {"name_nick", "biography", "demeanor", "nature"}
    )

    # FKs
    user_creator: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="created_characters", on_delete=fields.OnDelete.CASCADE
    )
    user_player: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="played_characters", on_delete=fields.OnDelete.CASCADE
    )
    company: fields.ForeignKeyRelation[Company] = fields.ForeignKeyField(
        "models.Company", related_name="characters", on_delete=fields.OnDelete.CASCADE
    )
    campaign: fields.ForeignKeyRelation[Campaign] = fields.ForeignKeyField(
        "models.Campaign", related_name="characters", on_delete=fields.OnDelete.CASCADE
    )
    concept: fields.ForeignKeyRelation[CharacterConcept] = fields.ForeignKeyField(
        "models.CharacterConcept",
        related_name="characters",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )

    # Reverse relations
    traits: fields.ReverseRelation[CharacterTrait]
    inventory: fields.ReverseRelation[CharacterInventory]
    specialties: fields.ReverseRelation[Specialty]
    vampire_attributes: fields.OneToOneRelation[VampireAttributes]
    werewolf_attributes: fields.OneToOneRelation[WerewolfAttributes]
    mage_attributes: fields.OneToOneRelation[MageAttributes]
    hunter_attributes: fields.OneToOneRelation[HunterAttributes]
    notes: fields.ReverseRelation[Note]
    dice_rolls: fields.ReverseRelation[DiceRoll]
    chargen_sessions: fields.ManyToManyRelation[ChargenSession]

    class Meta:
        """Tortoise ORM meta options."""

        table = "character"

    @property
    def name(self) -> str:
        """Full name: 'First Last'."""
        return f"{self.name_first} {self.name_last}"

    @property
    def name_full(self) -> str:
        """Full name with optional nickname: "First 'Nick' Last"."""
        if self.name_nick:
            return f"{self.name_first} '{self.name_nick}' {self.name_last}"
        return self.name

    @property
    def concept_name(self) -> str | None:
        """Name of the character concept, requires fetch_related('concept')."""
        return self.concept.name if self.concept else None


class VampireAttributes(BaseModel):
    """Vampire-specific attributes, one-to-one with Character."""

    character: fields.OneToOneRelation[Character] = fields.OneToOneField(
        "models.Character", related_name="vampire_attributes", on_delete=fields.OnDelete.CASCADE
    )
    clan: fields.ForeignKeyRelation[VampireClan] = fields.ForeignKeyField(
        "models.VampireClan",
        related_name="characters",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )
    generation = fields.IntField(null=True)
    sire = fields.CharField(max_length=50, null=True, validators=[MinLengthValidator(3)])
    bane_name = fields.CharField(max_length=50, null=True)
    bane_description = fields.TextField(null=True)
    compulsion_name = fields.CharField(max_length=50, null=True)
    compulsion_description = fields.TextField(null=True)

    _empty_string_to_none_fields: ClassVar[frozenset[str]] = frozenset({"sire"})

    class Meta:
        """Tortoise ORM meta options."""

        table = "vampire_attributes"

    @property
    def clan_name(self) -> str | None:
        """Name of the clan, requires fetch_related('clan')."""
        return self.clan.name if self.clan else None


class WerewolfAttributes(BaseModel):
    """Werewolf-specific attributes, one-to-one with Character."""

    character: fields.OneToOneRelation[Character] = fields.OneToOneField(
        "models.Character", related_name="werewolf_attributes", on_delete=fields.OnDelete.CASCADE
    )
    tribe: fields.ForeignKeyRelation[WerewolfTribe] = fields.ForeignKeyField(
        "models.WerewolfTribe",
        related_name="characters",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )
    auspice: fields.ForeignKeyRelation[WerewolfAuspice] = fields.ForeignKeyField(
        "models.WerewolfAuspice",
        related_name="characters",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )
    pack_name = fields.CharField(max_length=50, null=True, validators=[MinLengthValidator(3)])
    total_renown = fields.IntField(default=0)

    _empty_string_to_none_fields: ClassVar[frozenset[str]] = frozenset({"pack_name"})

    class Meta:
        """Tortoise ORM meta options."""

        table = "werewolf_attributes"

    @property
    def tribe_name(self) -> str | None:
        """Name of the tribe, requires fetch_related('tribe')."""
        return self.tribe.name if self.tribe else None

    @property
    def auspice_name(self) -> str | None:
        """Name of the auspice, requires fetch_related('auspice')."""
        return self.auspice.name if self.auspice else None


class MageAttributes(BaseModel):
    """Mage-specific attributes, one-to-one with Character."""

    character: fields.OneToOneRelation[Character] = fields.OneToOneField(
        "models.Character", related_name="mage_attributes", on_delete=fields.OnDelete.CASCADE
    )
    sphere = fields.CharField(max_length=50, null=True, validators=[MinLengthValidator(3)])
    tradition = fields.CharField(max_length=50, null=True, validators=[MinLengthValidator(3)])

    _empty_string_to_none_fields: ClassVar[frozenset[str]] = frozenset({"sphere", "tradition"})

    class Meta:
        """Tortoise ORM meta options."""

        table = "mage_attributes"


class HunterAttributes(BaseModel):
    """Hunter-specific attributes, one-to-one with Character."""

    character: fields.OneToOneRelation[Character] = fields.OneToOneField(
        "models.Character", related_name="hunter_attributes", on_delete=fields.OnDelete.CASCADE
    )
    creed = fields.CharField(max_length=50, null=True, validators=[MinLengthValidator(3)])

    _empty_string_to_none_fields: ClassVar[frozenset[str]] = frozenset({"creed"})

    class Meta:
        """Tortoise ORM meta options."""

        table = "hunter_attributes"


class CharacterTrait(BaseModel):
    """A trait assigned to a character with a numeric value."""

    character: fields.ForeignKeyRelation[Character] = fields.ForeignKeyField(
        "models.Character", related_name="traits", on_delete=fields.OnDelete.CASCADE
    )
    trait: fields.ForeignKeyRelation[Trait] = fields.ForeignKeyField(
        "models.Trait", related_name="character_traits", on_delete=fields.OnDelete.CASCADE
    )
    value = fields.IntField(default=0)

    class Meta:
        """Tortoise ORM meta options."""

        table = "character_trait"


class CharacterInventory(BaseModel):
    """An item in a character's inventory."""

    character: fields.ForeignKeyRelation[Character] = fields.ForeignKeyField(
        "models.Character", related_name="inventory", on_delete=fields.OnDelete.CASCADE
    )
    name = fields.CharField(max_length=50)
    description = fields.TextField(null=True)
    type = fields.CharEnumField(InventoryItemType)

    class Meta:
        """Tortoise ORM meta options."""

        table = "character_inventory"


class Specialty(BaseModel):
    """A character specialty."""

    character: fields.ForeignKeyRelation[Character] = fields.ForeignKeyField(
        "models.Character", related_name="specialties", on_delete=fields.OnDelete.CASCADE
    )
    name = fields.CharField(max_length=50)
    type = fields.CharEnumField(SpecialtyType)
    description = fields.TextField(null=True)

    class Meta:
        """Tortoise ORM meta options."""

        table = "specialty"
