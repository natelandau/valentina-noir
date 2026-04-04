"""Character blueprint response DTOs."""

from datetime import datetime
from uuid import UUID

import msgspec

from vapi.db.sql_models.character_classes import (
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import (
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)


class CharSheetSectionResponse(msgspec.Struct):
    """Character sheet section response."""

    id: UUID
    name: str
    description: str | None
    character_classes: list[str]
    game_versions: list[str]
    show_when_empty: bool
    order: int
    date_created: datetime
    date_modified: datetime

    @classmethod
    def from_model(cls, m: CharSheetSection) -> "CharSheetSectionResponse":
        """Convert a Tortoise CharSheetSection to a response Struct."""
        return cls(
            id=m.id,
            name=m.name,
            description=m.description,
            character_classes=m.character_classes or [],
            game_versions=m.game_versions or [],
            show_when_empty=m.show_when_empty,
            order=m.order,
            date_created=m.date_created,
            date_modified=m.date_modified,
        )


class TraitCategoryResponse(msgspec.Struct):
    """Trait category response."""

    id: UUID
    name: str
    description: str | None
    character_classes: list[str]
    game_versions: list[str]
    show_when_empty: bool
    order: int
    parent_sheet_section_id: UUID
    parent_sheet_section_name: str | None
    initial_cost: int
    upgrade_cost: int
    count_based_cost_multiplier: int | None
    date_created: datetime
    date_modified: datetime

    @classmethod
    def from_model(cls, m: TraitCategory) -> "TraitCategoryResponse":
        """Convert a Tortoise TraitCategory to a response Struct.

        Requires ``fetch_related("sheet_section")`` to populate the name property.
        """
        return cls(
            id=m.id,
            name=m.name,
            description=m.description,
            character_classes=m.character_classes or [],
            game_versions=m.game_versions or [],
            show_when_empty=m.show_when_empty,
            order=m.order,
            parent_sheet_section_id=m.sheet_section.id,
            parent_sheet_section_name=m.sheet_section_name,
            initial_cost=m.initial_cost,
            upgrade_cost=m.upgrade_cost,
            count_based_cost_multiplier=m.count_based_cost_multiplier,
            date_created=m.date_created,
            date_modified=m.date_modified,
        )


class TraitSubcategoryResponse(msgspec.Struct):
    """Trait subcategory response."""

    id: UUID
    name: str
    description: str | None
    character_classes: list[str]
    game_versions: list[str]
    show_when_empty: bool
    initial_cost: int
    upgrade_cost: int
    count_based_cost_multiplier: int | None
    requires_parent: bool
    pool: str | None
    system: str | None
    hunter_edge_type: str | None
    parent_category_id: UUID | None
    parent_category_name: str | None
    sheet_section_id: UUID | None
    sheet_section_name: str | None
    date_created: datetime
    date_modified: datetime

    @classmethod
    def from_model(cls, m: TraitSubcategory) -> "TraitSubcategoryResponse":
        """Convert a Tortoise TraitSubcategory to a response Struct.

        Requires ``fetch_related("category", "sheet_section")`` to populate name properties.
        """
        return cls(
            id=m.id,
            name=m.name,
            description=m.description,
            character_classes=m.character_classes or [],
            game_versions=m.game_versions or [],
            show_when_empty=m.show_when_empty,
            initial_cost=m.initial_cost,
            upgrade_cost=m.upgrade_cost,
            count_based_cost_multiplier=m.count_based_cost_multiplier,
            requires_parent=m.requires_parent,
            pool=m.pool,
            system=m.system,
            hunter_edge_type=m.hunter_edge_type.value if m.hunter_edge_type else None,
            parent_category_id=m.category.id if m.category else None,
            parent_category_name=m.category_name,
            sheet_section_id=m.sheet_section.id if m.sheet_section else None,
            sheet_section_name=m.sheet_section_name,
            date_created=m.date_created,
            date_modified=m.date_modified,
        )


class GiftAttributesResponse(msgspec.Struct):
    """Gift attributes nested in a trait response."""

    renown: str
    cost: str | None
    duration: str | None
    minimum_renown: int | None
    is_native_gift: bool
    tribe_id: UUID | None
    tribe_name: str | None
    auspice_id: UUID | None
    auspice_name: str | None


class NameDescriptionResponse(msgspec.Struct):
    """Name/description pair for vampire clan bane, compulsion, etc."""

    name: str | None
    description: str | None


class TraitResponse(msgspec.Struct):
    """Trait response."""

    id: UUID
    name: str
    description: str | None
    character_classes: list[str]
    game_versions: list[str]
    link: str | None
    show_when_zero: bool
    max_value: int
    min_value: int
    is_custom: bool
    initial_cost: int
    upgrade_cost: int
    count_based_cost_multiplier: int | None
    is_rollable: bool
    sheet_section_id: UUID
    sheet_section_name: str | None
    parent_category_id: UUID
    parent_category_name: str | None
    custom_for_character_id: UUID | None
    trait_subcategory_id: UUID | None
    trait_subcategory_name: str | None
    pool: str | None
    opposing_pool: str | None
    system: str | None
    gift_attributes: GiftAttributesResponse | None
    date_created: datetime
    date_modified: datetime

    @classmethod
    def from_model(cls, m: Trait) -> "TraitResponse":
        """Convert a Tortoise Trait to a response Struct.

        Requires ``fetch_related("category", "sheet_section", "subcategory",
        "gift_tribe", "gift_auspice")`` to populate name properties and gift attributes.
        """
        gift_attrs = None
        if m.gift_renown is not None:
            gift_attrs = GiftAttributesResponse(
                renown=m.gift_renown.value,
                cost=m.gift_cost,
                duration=m.gift_duration,
                minimum_renown=m.gift_minimum_renown,
                is_native_gift=m.gift_is_native or False,
                tribe_id=m.gift_tribe.id if m.gift_tribe else None,
                tribe_name=m.gift_tribe_name,
                auspice_id=m.gift_auspice.id if m.gift_auspice else None,
                auspice_name=m.gift_auspice_name,
            )

        return cls(
            id=m.id,
            name=m.name,
            description=m.description,
            character_classes=m.character_classes or [],
            game_versions=m.game_versions or [],
            link=m.link,
            show_when_zero=m.show_when_zero,
            max_value=m.max_value,
            min_value=m.min_value,
            is_custom=m.is_custom,
            initial_cost=m.initial_cost,
            upgrade_cost=m.upgrade_cost,
            count_based_cost_multiplier=m.count_based_cost_multiplier,
            is_rollable=m.is_rollable,
            sheet_section_id=m.sheet_section.id,
            sheet_section_name=m.sheet_section_name,
            parent_category_id=m.category.id,
            parent_category_name=m.category_name,
            custom_for_character_id=m.custom_for_character_id,
            trait_subcategory_id=m.subcategory.id if m.subcategory else None,
            trait_subcategory_name=m.subcategory_name,
            pool=m.pool,
            opposing_pool=m.opposing_pool,
            system=m.system,
            gift_attributes=gift_attrs,
            date_created=m.date_created,
            date_modified=m.date_modified,
        )


class CharacterConceptResponse(msgspec.Struct):
    """Character concept response (company_id excluded)."""

    id: UUID
    name: str
    description: str
    examples: list[str]
    max_specialties: int
    specialties: list[dict]
    favored_ability_names: list[str]
    date_created: datetime
    date_modified: datetime

    @classmethod
    def from_model(cls, m: CharacterConcept) -> "CharacterConceptResponse":
        """Convert a Tortoise CharacterConcept to a response Struct."""
        return cls(
            id=m.id,
            name=m.name,
            description=m.description,
            examples=m.examples or [],
            max_specialties=m.max_specialties,
            specialties=m.specialties or [],
            favored_ability_names=m.favored_ability_names or [],
            date_created=m.date_created,
            date_modified=m.date_modified,
        )


class VampireClanResponse(msgspec.Struct):
    """Vampire clan response."""

    id: UUID
    name: str
    description: str | None
    game_versions: list[str]
    discipline_ids: list[UUID]
    bane: NameDescriptionResponse | None
    variant_bane: NameDescriptionResponse | None
    compulsion: NameDescriptionResponse | None
    link: str | None
    date_created: datetime
    date_modified: datetime

    @classmethod
    def from_model(cls, m: VampireClan) -> "VampireClanResponse":
        """Convert a Tortoise VampireClan to a response Struct.

        Requires ``fetch_related("disciplines")`` to populate discipline_ids.
        """
        return cls(
            id=m.id,
            name=m.name,
            description=m.description,
            game_versions=m.game_versions or [],
            discipline_ids=[d.id for d in m.disciplines],
            bane=NameDescriptionResponse(name=m.bane_name, description=m.bane_description)
            if m.bane_name or m.bane_description
            else None,
            variant_bane=NameDescriptionResponse(
                name=m.variant_bane_name, description=m.variant_bane_description
            )
            if m.variant_bane_name or m.variant_bane_description
            else None,
            compulsion=NameDescriptionResponse(
                name=m.compulsion_name, description=m.compulsion_description
            )
            if m.compulsion_name or m.compulsion_description
            else None,
            link=m.link,
            date_created=m.date_created,
            date_modified=m.date_modified,
        )


class WerewolfAuspiceResponse(msgspec.Struct):
    """Werewolf auspice response."""

    id: UUID
    name: str
    description: str | None
    game_versions: list[str]
    gift_trait_ids: list[UUID]
    link: str | None
    date_created: datetime
    date_modified: datetime

    @classmethod
    def from_model(cls, m: WerewolfAuspice) -> "WerewolfAuspiceResponse":
        """Convert a Tortoise WerewolfAuspice to a response Struct.

        Requires ``fetch_related("gifts")`` to populate gift_trait_ids.
        """
        return cls(
            id=m.id,
            name=m.name,
            description=m.description,
            game_versions=m.game_versions or [],
            gift_trait_ids=[g.id for g in m.gifts],
            link=m.link,
            date_created=m.date_created,
            date_modified=m.date_modified,
        )


class WerewolfTribeResponse(msgspec.Struct):
    """Werewolf tribe response."""

    id: UUID
    name: str
    description: str | None
    game_versions: list[str]
    renown: str
    patron_spirit: str | None
    favor: str | None
    ban: str | None
    gift_trait_ids: list[UUID]
    link: str | None
    date_created: datetime
    date_modified: datetime

    @classmethod
    def from_model(cls, m: WerewolfTribe) -> "WerewolfTribeResponse":
        """Convert a Tortoise WerewolfTribe to a response Struct.

        Requires ``fetch_related("gifts")`` to populate gift_trait_ids.
        """
        return cls(
            id=m.id,
            name=m.name,
            description=m.description,
            game_versions=m.game_versions or [],
            renown=m.renown.value,
            patron_spirit=m.patron_spirit,
            favor=m.favor,
            ban=m.ban,
            gift_trait_ids=[g.id for g in m.gifts],
            link=m.link,
            date_created=m.date_created,
            date_modified=m.date_modified,
        )
