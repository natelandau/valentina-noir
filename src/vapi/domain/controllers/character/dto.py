"""Character DTOs — msgspec Structs for request/response bodies."""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

import msgspec

from vapi.constants import (
    CharacterClass,
    CharacterStatus,
    CharacterType,
    GameVersion,
    HunterEdgeType,
    SpecialtyType,
)
from vapi.domain.controllers.character_blueprint.dto import TraitResponse

if TYPE_CHECKING:
    from vapi.db.sql_models.character import (
        Character,
        CharacterTrait,
        HunterAttributes,
        MageAttributes,
        VampireAttributes,
        WerewolfAttributes,
    )
    from vapi.db.sql_models.character_sheet import (
        Trait,
        TraitCategory,
        TraitSubcategory,
    )


class CharacterInclude(StrEnum):
    """Child resources that can be embedded in a character detail response."""

    TRAITS = "traits"
    INVENTORY = "inventory"
    NOTES = "notes"
    ASSETS = "assets"


INCLUDE_PREFETCH_MAP: dict[CharacterInclude, list[str]] = {
    CharacterInclude.TRAITS: [
        "traits__trait",
        "traits__trait__category",
        "traits__trait__subcategory",
        "traits__trait__sheet_section",
    ],
    CharacterInclude.INVENTORY: ["inventory"],
    CharacterInclude.NOTES: ["notes"],
    CharacterInclude.ASSETS: ["assets"],
}


# ---------------------------------------------------------------------------
# Attribute sub-Structs (response)
# ---------------------------------------------------------------------------


class VampireAttributesResponse(msgspec.Struct):
    """Vampire-specific attributes in a character response."""

    clan_id: UUID | None
    clan_name: str | None
    generation: int | None
    sire: str | None
    bane_name: str | None
    bane_description: str | None
    compulsion_name: str | None
    compulsion_description: str | None

    @classmethod
    def from_model(cls, m: "VampireAttributes") -> "VampireAttributesResponse":
        """Convert a Tortoise VampireAttributes to a response Struct.

        Requires fetch_related('clan') for clan_name.
        """
        return cls(
            clan_id=m.clan_id,  # type: ignore[attr-defined]
            clan_name=m.clan_name,
            generation=m.generation,
            sire=m.sire,
            bane_name=m.bane_name,
            bane_description=m.bane_description,
            compulsion_name=m.compulsion_name,
            compulsion_description=m.compulsion_description,
        )


class WerewolfAttributesResponse(msgspec.Struct):
    """Werewolf-specific attributes in a character response."""

    tribe_id: UUID | None
    tribe_name: str | None
    auspice_id: UUID | None
    auspice_name: str | None
    pack_name: str | None
    total_renown: int

    @classmethod
    def from_model(cls, m: "WerewolfAttributes") -> "WerewolfAttributesResponse":
        """Convert a Tortoise WerewolfAttributes to a response Struct.

        Requires fetch_related('tribe', 'auspice') for name properties.
        """
        return cls(
            tribe_id=m.tribe_id,  # type: ignore[attr-defined]
            tribe_name=m.tribe_name,
            auspice_id=m.auspice_id,  # type: ignore[attr-defined]
            auspice_name=m.auspice_name,
            pack_name=m.pack_name,
            total_renown=m.total_renown,
        )


class MageAttributesResponse(msgspec.Struct):
    """Mage-specific attributes in a character response."""

    sphere: str | None
    tradition: str | None

    @classmethod
    def from_model(cls, m: "MageAttributes") -> "MageAttributesResponse":
        """Convert a Tortoise MageAttributes to a response Struct."""
        return cls(sphere=m.sphere, tradition=m.tradition)


class HunterAttributesResponse(msgspec.Struct):
    """Hunter-specific attributes in a character response."""

    creed: str | None

    @classmethod
    def from_model(cls, m: "HunterAttributes") -> "HunterAttributesResponse":
        """Convert a Tortoise HunterAttributes to a response Struct."""
        return cls(creed=m.creed)


class SpecialtyResponse(msgspec.Struct):
    """Specialty in a character response."""

    id: UUID
    name: str
    type: SpecialtyType
    description: str | None


# ---------------------------------------------------------------------------
# Character response
# ---------------------------------------------------------------------------

# Relations that must be prefetched for CharacterResponse.from_model()
CHARACTER_RESPONSE_PREFETCH: list[str] = [
    "concept",
    "vampire_attributes__clan",
    "werewolf_attributes__tribe",
    "werewolf_attributes__auspice",
    "mage_attributes",
    "hunter_attributes",
    "specialties",
]


class CharacterResponse(msgspec.Struct):
    """Response body for a character."""

    id: UUID
    name_first: str
    name_last: str
    name_nick: str | None
    name: str
    name_full: str
    character_class: CharacterClass
    type: CharacterType
    game_version: GameVersion
    status: CharacterStatus
    starting_points: int
    age: int | None
    biography: str | None
    demeanor: str | None
    nature: str | None
    concept_id: UUID | None
    concept_name: str | None
    is_temporary: bool
    date_killed: datetime | None
    user_creator_id: UUID
    user_player_id: UUID
    company_id: UUID
    campaign_id: UUID
    specialties: list[SpecialtyResponse]
    vampire_attributes: VampireAttributesResponse | None
    werewolf_attributes: WerewolfAttributesResponse | None
    mage_attributes: MageAttributesResponse | None
    hunter_attributes: HunterAttributesResponse | None
    date_created: datetime
    date_modified: datetime
    is_archived: bool

    @classmethod
    def from_model(cls, m: "Character") -> "CharacterResponse":
        """Convert a Tortoise Character to a response Struct.

        Requires prefetch_related('concept', 'vampire_attributes__clan',
        'werewolf_attributes__tribe', 'werewolf_attributes__auspice',
        'mage_attributes', 'hunter_attributes', 'specialties').
        """
        vampire_resp = None
        werewolf_resp = None
        mage_resp = None
        hunter_resp = None

        try:
            va = m.vampire_attributes
            if va:
                vampire_resp = VampireAttributesResponse.from_model(va)
        except Exception:  # noqa: BLE001, S110
            pass

        try:
            wa = m.werewolf_attributes
            if wa:
                werewolf_resp = WerewolfAttributesResponse.from_model(wa)
        except Exception:  # noqa: BLE001, S110
            pass

        try:
            ma = m.mage_attributes
            if ma:
                mage_resp = MageAttributesResponse.from_model(ma)
        except Exception:  # noqa: BLE001, S110
            pass

        try:
            ha = m.hunter_attributes
            if ha:
                hunter_resp = HunterAttributesResponse.from_model(ha)
        except Exception:  # noqa: BLE001, S110
            pass

        specialties_list: list[SpecialtyResponse] = []
        try:  # noqa: SIM105
            specialties_list.extend(
                SpecialtyResponse(id=s.id, name=s.name, type=s.type, description=s.description)
                for s in m.specialties
            )
        except Exception:  # noqa: BLE001, S110
            pass

        return cls(
            id=m.id,
            name_first=m.name_first,
            name_last=m.name_last,
            name_nick=m.name_nick,
            name=m.name,
            name_full=m.name_full,
            character_class=m.character_class,
            type=m.type,
            game_version=m.game_version,
            status=m.status,
            starting_points=m.starting_points,
            age=m.age,
            biography=m.biography,
            demeanor=m.demeanor,
            nature=m.nature,
            concept_id=m.concept_id,  # type: ignore[attr-defined]
            concept_name=m.concept_name,
            is_temporary=m.is_temporary,
            date_killed=m.date_killed,
            user_creator_id=m.user_creator_id,  # type: ignore[attr-defined]
            user_player_id=m.user_player_id,  # type: ignore[attr-defined]
            company_id=m.company_id,  # type: ignore[attr-defined]
            campaign_id=m.campaign_id,  # type: ignore[attr-defined]
            specialties=specialties_list,
            vampire_attributes=vampire_resp,
            werewolf_attributes=werewolf_resp,
            mage_attributes=mage_resp,
            hunter_attributes=hunter_resp,
            date_created=m.date_created,
            date_modified=m.date_modified,
            is_archived=m.is_archived,
        )


# ---------------------------------------------------------------------------
# Attribute sub-Structs (request — create)
# ---------------------------------------------------------------------------


class VampireAttributesCreate(msgspec.Struct):
    """Vampire attributes for character creation."""

    clan_id: UUID
    generation: int | None = None
    sire: str | None = None
    bane_name: str | None = None
    bane_description: str | None = None
    compulsion_name: str | None = None
    compulsion_description: str | None = None


class WerewolfAttributesCreate(msgspec.Struct):
    """Werewolf attributes for character creation."""

    tribe_id: UUID
    auspice_id: UUID
    pack_name: str | None = None


class MageAttributesCreate(msgspec.Struct):
    """Mage attributes for character creation."""

    sphere: str | None = None
    tradition: str | None = None


class HunterAttributesCreate(msgspec.Struct):
    """Hunter attributes for character creation."""

    creed: str | None = None


# ---------------------------------------------------------------------------
# Attribute sub-Structs (request — patch)
# ---------------------------------------------------------------------------


class VampireAttributesPatch(msgspec.Struct):
    """Vampire attributes for character patch."""

    clan_id: UUID | msgspec.UnsetType = msgspec.UNSET
    generation: int | None | msgspec.UnsetType = msgspec.UNSET
    sire: str | None | msgspec.UnsetType = msgspec.UNSET
    bane_name: str | None | msgspec.UnsetType = msgspec.UNSET
    bane_description: str | None | msgspec.UnsetType = msgspec.UNSET
    compulsion_name: str | None | msgspec.UnsetType = msgspec.UNSET
    compulsion_description: str | None | msgspec.UnsetType = msgspec.UNSET


class WerewolfAttributesPatch(msgspec.Struct):
    """Werewolf attributes for character patch."""

    tribe_id: UUID | msgspec.UnsetType = msgspec.UNSET
    auspice_id: UUID | msgspec.UnsetType = msgspec.UNSET
    pack_name: str | None | msgspec.UnsetType = msgspec.UNSET


class MageAttributesPatch(msgspec.Struct):
    """Mage attributes for character patch."""

    sphere: str | None | msgspec.UnsetType = msgspec.UNSET
    tradition: str | None | msgspec.UnsetType = msgspec.UNSET


class HunterAttributesPatch(msgspec.Struct):
    """Hunter attributes for character patch."""

    creed: str | None | msgspec.UnsetType = msgspec.UNSET


# ---------------------------------------------------------------------------
# Character request DTOs
# ---------------------------------------------------------------------------


class CharacterTraitCreate(msgspec.Struct):
    """Trait to assign during character creation."""

    trait_id: UUID
    value: int = 0


class CharacterCreate(msgspec.Struct):
    """Request body for creating a character."""

    name_first: str
    name_last: str
    character_class: CharacterClass
    game_version: GameVersion
    name_nick: str | None = None
    type: CharacterType = CharacterType.PLAYER
    age: int | None = None
    biography: str | None = None
    demeanor: str | None = None
    nature: str | None = None
    concept_id: UUID | None = None
    vampire_attributes: VampireAttributesCreate | None = None
    werewolf_attributes: WerewolfAttributesCreate | None = None
    mage_attributes: MageAttributesCreate | None = None
    hunter_attributes: HunterAttributesCreate | None = None
    traits: list[CharacterTraitCreate] = []
    user_player_id: UUID | None = None


class CharacterPatch(msgspec.Struct):
    """Request body for partially updating a character.

    All fields use UNSET as default to distinguish 'not sent' from 'sent as null'.
    """

    name_first: str | msgspec.UnsetType = msgspec.UNSET
    name_last: str | msgspec.UnsetType = msgspec.UNSET
    name_nick: str | None | msgspec.UnsetType = msgspec.UNSET
    type: CharacterType | msgspec.UnsetType = msgspec.UNSET
    status: CharacterStatus | msgspec.UnsetType = msgspec.UNSET
    age: int | None | msgspec.UnsetType = msgspec.UNSET
    biography: str | None | msgspec.UnsetType = msgspec.UNSET
    demeanor: str | None | msgspec.UnsetType = msgspec.UNSET
    nature: str | None | msgspec.UnsetType = msgspec.UNSET
    concept_id: UUID | None | msgspec.UnsetType = msgspec.UNSET
    is_temporary: bool | msgspec.UnsetType = msgspec.UNSET
    user_player_id: UUID | msgspec.UnsetType = msgspec.UNSET
    vampire_attributes: VampireAttributesPatch | msgspec.UnsetType = msgspec.UNSET
    werewolf_attributes: WerewolfAttributesPatch | msgspec.UnsetType = msgspec.UNSET
    mage_attributes: MageAttributesPatch | msgspec.UnsetType = msgspec.UNSET
    hunter_attributes: HunterAttributesPatch | msgspec.UnsetType = msgspec.UNSET


# ---------------------------------------------------------------------------
# Full sheet DTOs
# ---------------------------------------------------------------------------


class FullSheetCharacterTraitDTO(msgspec.Struct):
    """A character trait on the full sheet."""

    id: UUID
    value: int
    character_id: UUID
    trait: TraitResponse

    @classmethod
    def from_model(cls, ct: "CharacterTrait") -> "FullSheetCharacterTraitDTO":
        """Convert a Tortoise CharacterTrait (with prefetched trait) to a DTO."""
        return cls(
            id=ct.id,
            value=ct.value,
            character_id=ct.character_id,  # type: ignore[attr-defined]
            trait=TraitResponse.from_model(ct.trait),
        )


class FullSheetTraitSubcategoryDTO(msgspec.Struct):
    """A trait subcategory on the full sheet."""

    id: UUID
    name: str
    description: str | None
    initial_cost: int
    upgrade_cost: int
    show_when_empty: bool
    requires_parent: bool
    pool: str | None
    system: str | None
    hunter_edge_type: HunterEdgeType | None
    character_traits: list[FullSheetCharacterTraitDTO]
    available_traits: list[TraitResponse]

    @classmethod
    def build(
        cls,
        subcategory: "TraitSubcategory",
        character_traits: list["CharacterTrait"],
        available_traits: list["Trait"],
    ) -> "FullSheetTraitSubcategoryDTO":
        """Build from a subcategory model, its character traits, and available traits."""
        return cls(
            id=subcategory.id,
            name=subcategory.name,
            description=subcategory.description,
            show_when_empty=subcategory.show_when_empty,
            initial_cost=subcategory.initial_cost,
            upgrade_cost=subcategory.upgrade_cost,
            requires_parent=subcategory.requires_parent,
            pool=subcategory.pool,
            system=subcategory.system,
            hunter_edge_type=subcategory.hunter_edge_type,
            character_traits=[FullSheetCharacterTraitDTO.from_model(ct) for ct in character_traits],
            available_traits=[TraitResponse.from_model(t) for t in available_traits],
        )


class FullSheetTraitCategoryDTO(msgspec.Struct):
    """A trait category on the full sheet."""

    id: UUID
    name: str
    description: str | None
    initial_cost: int
    upgrade_cost: int
    show_when_empty: bool
    order: int
    subcategories: list[FullSheetTraitSubcategoryDTO]
    character_traits: list[FullSheetCharacterTraitDTO]
    available_traits: list[TraitResponse]

    @classmethod
    def build(
        cls,
        category: "TraitCategory",
        subcategories: list["TraitSubcategory"],
        traits_by_subcategory: dict[UUID, list["CharacterTrait"]],
        category_traits_no_sub: list["CharacterTrait"],
        available_by_subcategory: dict[UUID, list["Trait"]],
        available_by_category_no_sub: dict[UUID, list["Trait"]],
    ) -> "FullSheetTraitCategoryDTO":
        """Build from a category model with all child data."""
        return cls(
            id=category.id,
            name=category.name,
            description=category.description,
            order=category.order,
            show_when_empty=category.show_when_empty,
            initial_cost=category.initial_cost,
            upgrade_cost=category.upgrade_cost,
            subcategories=[
                FullSheetTraitSubcategoryDTO.build(
                    subcategory=sub,
                    character_traits=traits_by_subcategory.get(sub.id, []),
                    available_traits=available_by_subcategory.get(sub.id, []),
                )
                for sub in subcategories
            ],
            character_traits=[
                FullSheetCharacterTraitDTO.from_model(ct) for ct in category_traits_no_sub
            ],
            available_traits=[
                TraitResponse.from_model(t)
                for t in available_by_category_no_sub.get(category.id, [])
            ],
        )


class FullSheetTraitSectionDTO(msgspec.Struct):
    """A trait section on the full sheet."""

    id: UUID
    name: str
    description: str | None
    order: int
    show_when_empty: bool
    categories: list[FullSheetTraitCategoryDTO]


class CharacterFullSheetDTO(msgspec.Struct):
    """A character full sheet."""

    sections: list[FullSheetTraitSectionDTO]
    character: CharacterResponse

    @classmethod
    def build(
        cls,
        character: "Character",
        sections: list[FullSheetTraitSectionDTO],
    ) -> "CharacterFullSheetDTO":
        """Build from a character and pre-assembled sections."""
        return cls(
            character=CharacterResponse.from_model(character),
            sections=sections,
        )


class CharacterDetailResponse(CharacterResponse, omit_defaults=True):
    """Response body for a single character with optional embedded children.

    Inherits all fields from CharacterResponse and adds optional child lists.
    When no includes are requested, the serialized JSON is identical to
    CharacterResponse (child fields are omitted via omit_defaults).
    """

    # Optional children — omitted from JSON when not requested.
    # Types use msgspec.Struct base because the concrete DTO modules can't be
    # imported at module level without causing circular imports.
    traits: list[msgspec.Struct] | msgspec.UnsetType = msgspec.UNSET
    inventory: list[msgspec.Struct] | msgspec.UnsetType = msgspec.UNSET
    notes: list[msgspec.Struct] | msgspec.UnsetType = msgspec.UNSET
    assets: list[msgspec.Struct] | msgspec.UnsetType = msgspec.UNSET

    @classmethod
    def from_model(
        cls,
        m: "Character",
        includes: set[CharacterInclude] | None = None,
    ) -> "CharacterDetailResponse":
        """Convert a Tortoise Character to a detail response.

        Delegate base fields to CharacterResponse.from_model(), then conditionally
        populate child lists based on the requested includes.

        Args:
            m: The Character model instance with relations prefetched.
            includes: Set of CharacterInclude values indicating which children to embed.
        """
        # Lazy imports to avoid circular dependency: these controller dto modules
        # import from deps.py which imports from this file at module level.
        from vapi.domain.controllers.character_inventory.dto import InventoryItemResponse
        from vapi.domain.controllers.character_trait.dto import CharacterTraitResponse
        from vapi.domain.controllers.notes.dto import NoteResponse
        from vapi.domain.controllers.s3_assets.dto import S3AssetResponse

        includes = includes or set()
        base = CharacterResponse.from_model(m)

        # Build base field dict, then overlay optional children
        fields: dict[str, object] = {f: getattr(base, f) for f in base.__struct_fields__}
        if CharacterInclude.TRAITS in includes:
            fields["traits"] = [CharacterTraitResponse.from_model(t) for t in m.traits]
        if CharacterInclude.INVENTORY in includes:
            fields["inventory"] = [InventoryItemResponse.from_model(i) for i in m.inventory]
        if CharacterInclude.NOTES in includes:
            fields["notes"] = [NoteResponse.from_model(n) for n in m.notes]
        if CharacterInclude.ASSETS in includes:
            fields["assets"] = [S3AssetResponse.from_model(a) for a in m.assets]

        return cls(**fields)  # type: ignore[arg-type]
