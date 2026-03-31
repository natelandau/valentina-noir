"""Character sheet structure models: sections, categories, subcategories, traits."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tortoise import fields

from vapi.constants import HunterEdgeType, WerewolfRenown
from vapi.db.sql_models.base import BaseModel
from vapi.db.sql_models.validators import validate_character_classes, validate_game_versions

if TYPE_CHECKING:
    from vapi.db.sql_models.character import CharacterTrait
    from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
    from vapi.db.sql_models.diceroll import DiceRoll
    from vapi.db.sql_models.quickroll import QuickRoll


class CharSheetSection(BaseModel):
    """A section on the character sheet (e.g., 'Attributes', 'Skills')."""

    name = fields.CharField(max_length=50)
    description = fields.TextField(null=True)
    character_classes: Any = fields.JSONField(default=list, validators=[validate_character_classes])
    game_versions: Any = fields.JSONField(default=list, validators=[validate_game_versions])
    show_when_empty = fields.BooleanField(default=False)
    order = fields.IntField(default=0)

    # Reverse relations
    categories: fields.ReverseRelation[TraitCategory]
    subcategories: fields.ReverseRelation[TraitSubcategory]
    traits: fields.ReverseRelation[Trait]

    class Meta:
        """Tortoise ORM meta options."""

        table = "char_sheet_section"


class TraitCategory(BaseModel):
    """A category within a character sheet section (e.g., 'Physical', 'Mental')."""

    name = fields.CharField(max_length=50)
    description = fields.TextField(null=True)
    character_classes: Any = fields.JSONField(default=list, validators=[validate_character_classes])
    game_versions: Any = fields.JSONField(default=list, validators=[validate_game_versions])
    show_when_empty = fields.BooleanField(default=False)
    order = fields.IntField(default=0)
    initial_cost = fields.IntField(default=0)
    upgrade_cost = fields.IntField(default=0)
    count_based_cost_multiplier = fields.IntField(null=True)

    sheet_section: fields.ForeignKeyRelation[CharSheetSection] = fields.ForeignKeyField(
        "models.CharSheetSection", related_name="categories", on_delete=fields.OnDelete.CASCADE
    )

    # Reverse relations
    subcategories: fields.ReverseRelation[TraitSubcategory]
    traits: fields.ReverseRelation[Trait]

    class Meta:
        """Tortoise ORM meta options."""

        table = "trait_category"

    @property
    def sheet_section_name(self) -> str | None:
        """Name of the parent sheet section, requires fetch_related('sheet_section')."""
        return self.sheet_section.name if self.sheet_section else None


class TraitSubcategory(BaseModel):
    """A subcategory within a trait category."""

    name = fields.CharField(max_length=50)
    description = fields.TextField(null=True)
    character_classes: Any = fields.JSONField(default=list, validators=[validate_character_classes])
    game_versions: Any = fields.JSONField(default=list, validators=[validate_game_versions])
    show_when_empty = fields.BooleanField(default=False)
    initial_cost = fields.IntField(default=0)
    upgrade_cost = fields.IntField(default=0)
    count_based_cost_multiplier = fields.IntField(null=True)
    requires_parent = fields.BooleanField(default=False)
    pool = fields.TextField(null=True)
    system = fields.TextField(null=True)
    hunter_edge_type = fields.CharEnumField(HunterEdgeType, null=True)

    category: fields.ForeignKeyRelation[TraitCategory] = fields.ForeignKeyField(
        "models.TraitCategory", related_name="subcategories", on_delete=fields.OnDelete.CASCADE
    )
    sheet_section: fields.ForeignKeyRelation[CharSheetSection] = fields.ForeignKeyField(
        "models.CharSheetSection",
        related_name="subcategories",
        on_delete=fields.OnDelete.CASCADE,
        null=True,
    )

    # Reverse relations
    traits: fields.ReverseRelation[Trait]

    class Meta:
        """Tortoise ORM meta options."""

        table = "trait_subcategory"

    @property
    def category_name(self) -> str | None:
        """Name of the parent category, requires fetch_related('category')."""
        return self.category.name if self.category else None

    @property
    def sheet_section_name(self) -> str | None:
        """Name of the parent sheet section, requires fetch_related('sheet_section')."""
        return self.sheet_section.name if self.sheet_section else None


class Trait(BaseModel):
    """A trait that can be assigned to characters. Gift attributes are nullable columns."""

    name = fields.CharField(max_length=50)
    description = fields.TextField(null=True)
    character_classes: Any = fields.JSONField(default=list, validators=[validate_character_classes])
    game_versions: Any = fields.JSONField(default=list, validators=[validate_game_versions])
    link = fields.TextField(null=True)
    show_when_zero = fields.BooleanField(default=False)
    max_value = fields.IntField(default=5)
    min_value = fields.IntField(default=0)
    is_custom = fields.BooleanField(default=False)
    initial_cost = fields.IntField(default=0)
    upgrade_cost = fields.IntField(default=0)
    count_based_cost_multiplier = fields.IntField(null=True)
    is_rollable = fields.BooleanField(default=False)
    pool = fields.TextField(null=True)
    opposing_pool = fields.TextField(null=True)
    system = fields.TextField(null=True)
    custom_for_character_id = fields.UUIDField(null=True)

    # FK relationships
    category: fields.ForeignKeyRelation[TraitCategory] = fields.ForeignKeyField(
        "models.TraitCategory", related_name="traits", on_delete=fields.OnDelete.CASCADE
    )
    subcategory: fields.ForeignKeyRelation[TraitSubcategory] = fields.ForeignKeyField(
        "models.TraitSubcategory",
        related_name="traits",
        on_delete=fields.OnDelete.CASCADE,
        null=True,
    )
    sheet_section: fields.ForeignKeyRelation[CharSheetSection] = fields.ForeignKeyField(
        "models.CharSheetSection", related_name="traits", on_delete=fields.OnDelete.CASCADE
    )

    # Gift attributes (nullable, only set for werewolf gifts)
    gift_renown = fields.CharEnumField(WerewolfRenown, null=True)
    gift_cost = fields.CharField(max_length=50, null=True)
    gift_duration = fields.CharField(max_length=50, null=True)
    gift_minimum_renown = fields.IntField(null=True)
    gift_is_native = fields.BooleanField(null=True)
    gift_tribe: fields.ForeignKeyRelation[WerewolfTribe] = fields.ForeignKeyField(
        "models.WerewolfTribe",
        related_name="gift_traits",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )
    gift_auspice: fields.ForeignKeyRelation[WerewolfAuspice] = fields.ForeignKeyField(
        "models.WerewolfAuspice",
        related_name="gift_traits",
        on_delete=fields.OnDelete.SET_NULL,
        null=True,
    )

    # Reverse relations
    clans: fields.ReverseRelation[VampireClan]
    auspices: fields.ReverseRelation[WerewolfAuspice]
    tribes: fields.ReverseRelation[WerewolfTribe]
    character_traits: fields.ReverseRelation[CharacterTrait]
    dice_rolls: fields.ManyToManyRelation[DiceRoll]
    quick_rolls: fields.ManyToManyRelation[QuickRoll]

    class Meta:
        """Tortoise ORM meta options."""

        table = "trait"

    @property
    def category_name(self) -> str | None:
        """Name of the parent category, requires fetch_related('category')."""
        return self.category.name if self.category else None

    @property
    def subcategory_name(self) -> str | None:
        """Name of the parent subcategory, requires fetch_related('subcategory')."""
        return self.subcategory.name if self.subcategory else None

    @property
    def sheet_section_name(self) -> str | None:
        """Name of the parent sheet section, requires fetch_related('sheet_section')."""
        return self.sheet_section.name if self.sheet_section else None

    @property
    def gift_tribe_name(self) -> str | None:
        """Name of the gift tribe, requires fetch_related('gift_tribe')."""
        return self.gift_tribe.name if self.gift_tribe else None

    @property
    def gift_auspice_name(self) -> str | None:
        """Name of the gift auspice, requires fetch_related('gift_auspice')."""
        return self.gift_auspice.name if self.gift_auspice else None
