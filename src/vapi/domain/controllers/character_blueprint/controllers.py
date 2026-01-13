"""Character blueprint controllers."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from beanie.operators import Or
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get
from litestar.params import Parameter

from vapi.constants import CharacterClass, GameVersion, HunterEdgeType  # noqa: TC001
from vapi.db.models import (
    CharacterConcept,
    CharSheetSection,
    Company,
    HunterEdge,
    HunterEdgePerk,
    Trait,
    TraitCategory,
    VampireClan,
    WerewolfAuspice,
    WerewolfGift,
    WerewolfRite,
    WerewolfTribe,
)
from vapi.domain import deps, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CharacterBlueprintService
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import dto, schemas


class CharacterBlueprintSectionController(Controller):
    """Character blueprint sections controller."""

    tags = [APITags.CHARACTERS_BLUEPRINTS.name]
    dependencies = {
        "company": Provide(deps.provide_company_by_id),
    }
    guards = [developer_company_user_guard]

    ## SHEET SECTIONS #######################################################
    @get(
        path=urls.CharacterBlueprints.SECTIONS,
        summary="List sheet sections",
        operation_id="listCharacterBlueprintSections",
        description="Retrieve character sheet sections for a game version. Sections organize trait categories (e.g., Attributes, Abilities, Backgrounds). Optionally filter by character class.",
        cache=True,
        return_dto=dto.CharacterSheetDTO,
    )
    async def list_character_blueprint_sections(
        self,
        game_version: GameVersion,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        character_class: Annotated[
            CharacterClass,
            Parameter(
                description="Show character blueprint sections for this class.",
                title="Character Class",
            ),
        ]
        | None = None,
    ) -> OffsetPagination[CharSheetSection]:
        """List all character blueprint sections."""
        service = CharacterBlueprintService()
        count, sections = await service.list_sheet_sections(
            game_version=game_version,
            character_class=character_class,
            limit=limit,
            offset=offset,
        )
        return OffsetPagination(items=sections, limit=limit, offset=offset, total=count)

    @get(
        path=urls.CharacterBlueprints.SECTION_DETAIL,
        summary="Get sheet section",
        operation_id="getCharacterBlueprintSection",
        description="Retrieve a specific character sheet section including its metadata and ordering.",
        cache=True,
        return_dto=dto.CharacterSheetDTO,
        dependencies={
            "section": Provide(deps.provide_character_blueprint_section_by_id),
        },
    )
    async def get_character_blueprint_section(
        self, *, section: CharSheetSection
    ) -> CharSheetSection:
        """Get a character blueprint section by ID."""
        return section

    ## SECTION CATEGORIES #######################################################
    @get(
        path=urls.CharacterBlueprints.CATEGORIES,
        summary="List trait categories",
        operation_id="listCharacterBlueprintCategories",
        description="Retrieve trait categories within a sheet section for a game version. Categories group related traits (e.g., Physical, Social, Mental attributes). Optionally filter by character class.",
        cache=True,
        return_dto=dto.TraitCategoryDTO,
        dependencies={
            "section": Provide(deps.provide_character_blueprint_section_by_id),
        },
    )
    async def list_character_blueprint_categories(
        self,
        *,
        game_version: GameVersion,
        section: CharSheetSection,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        character_class: Annotated[
            CharacterClass,
            Parameter(
                description="Show all trait categories filtered for this class.",
                title="Character Class",
            ),
        ]
        | None = None,
    ) -> OffsetPagination[TraitCategory]:
        """List all character blueprint categories."""
        service = CharacterBlueprintService()
        count, categories = await service.list_sheet_categories(
            game_version=game_version,
            section=section,
            character_class=character_class,
            limit=limit,
            offset=offset,
        )
        return OffsetPagination(items=categories, limit=limit, offset=offset, total=count)

    @get(
        path=urls.CharacterBlueprints.CATEGORY_DETAIL,
        summary="Get trait category",
        operation_id="getCharacterBlueprintCategory",
        description="Retrieve a specific trait category including its cost configuration and metadata.",
        cache=True,
        return_dto=dto.TraitCategoryDTO,
        dependencies={
            "category": Provide(deps.provide_trait_category_by_id),
        },
    )
    async def get_character_blueprint_category(self, *, category: TraitCategory) -> TraitCategory:
        """Get a character sheet category by ID."""
        return category

    ## CATEGORY TRAITS #######################################################
    @get(
        path=urls.CharacterBlueprints.CATEGORY_TRAITS,
        summary="List category traits",
        operation_id="listCharacterBlueprintCategoryTraits",
        description="Retrieve traits within a category for a game version. These are the individual traits that can be assigned to characters (e.g., Strength, Firearms, Resources). Optionally filter by character class or character ID for custom traits.",
        cache=True,
        return_dto=dto.TraitDTO,
        dependencies={
            "category": Provide(deps.provide_trait_category_by_id),
        },
    )
    async def list_character_blueprint_category_traits(
        self,
        *,
        game_version: GameVersion,
        category: TraitCategory,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        character_class: Annotated[
            CharacterClass,
            Parameter(
                description="Show character sheet sections for this class.",
                title="Character Class",
            ),
        ]
        | None = None,
        character_id: Annotated[
            PydanticObjectId,
            Parameter(
                description="Include custom traits assigned to this character.",
                title="Character ID",
            ),
        ]
        | None = None,
    ) -> OffsetPagination[Trait]:
        """List all character sheet category traits."""
        service = CharacterBlueprintService()
        count, traits = await service.list_sheet_category_traits(
            game_version=game_version,
            category=category,
            character_class=character_class,
            character_id=character_id,
            limit=limit,
            offset=offset,
        )
        return OffsetPagination(items=traits, limit=limit, offset=offset, total=count)

    @get(
        path=urls.CharacterBlueprints.TRAIT_DETAIL,
        summary="Get trait",
        operation_id="getCharacterBlueprintCategoryTrait",
        description="Retrieve a specific trait including its value range, cost configuration, and metadata.",
        cache=True,
        return_dto=dto.TraitDTO,
        dependencies={
            "trait": Provide(deps.provide_trait_by_id),
        },
    )
    async def get_character_blueprint_category_trait(self, *, trait: Trait) -> Trait:
        """Get a character sheet category trait by ID."""
        return trait

    ## ALL TRAITS #######################################################
    @get(
        path=urls.CharacterBlueprints.TRAITS,
        summary="List all traits",
        operation_id="listAllCharacterBlueprintTraits",
        description="Retrieve all system traits regardless of game version or character class. Excludes custom character-specific traits. Useful for building trait selection interfaces or validating trait references.",
        cache=True,
        return_dto=dto.TraitDTO,
    )
    async def list_all_character_blueprint_traits(
        self,
        *,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        game_version: Annotated[
            GameVersion | None,
            Parameter(description="Show traits for this game version.", title="Game Version"),
        ] = None,
        character_class: Annotated[
            CharacterClass | None,
            Parameter(description="Show traits for this character class.", title="Character Class"),
        ] = None,
        parent_category_id: Annotated[
            PydanticObjectId | None,
            Parameter(description="Show traits for this category.", title="Category ID"),
        ] = None,
        order_by: Annotated[
            schemas.TraitSort,
            Parameter(description="Sort traits by this field.", title="Sort"),
        ] = schemas.TraitSort.NAME,
    ) -> OffsetPagination[Trait]:
        """List all constant character traits."""
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(
            game_version=game_version,
            character_class=character_class,
            parent_category_id=parent_category_id,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return OffsetPagination(items=traits, limit=limit, offset=offset, total=count)

    ## Classes, Concepts, and class specific options ############################################

    @get(
        path=urls.CharacterBlueprints.CONCEPTS,
        summary="List concepts",
        operation_id="listCharacterBlueprintConcepts",
        description="Retrieve all concepts.",
        cache=True,
        return_dto=dto.ConceptDTO,
    )
    async def list_character_blueprint_concepts(
        self,
        *,
        company: Company,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[CharacterConcept]:
        """List all concepts."""
        filters = [
            CharacterConcept.is_archived == False,
            Or(CharacterConcept.company_id == company.id, CharacterConcept.company_id == None),
        ]

        count = await CharacterConcept.find(*filters).count()  # type: ignore [call-overload]
        concepts = (
            await CharacterConcept.find(*filters).skip(offset).limit(limit).sort("name").to_list()  # type: ignore [call-overload]
        )
        return OffsetPagination(items=concepts, limit=limit, offset=offset, total=count)

    @get(
        path=urls.CharacterBlueprints.CONCEPT_DETAIL,
        summary="Get concept",
        operation_id="getCharacterBlueprintConcept",
        description="Retrieve a specific concept including its name, description, and examples.",
        cache=True,
        return_dto=dto.ConceptDTO,
        dependencies={
            "concept": Provide(deps.provide_character_concept_by_id),
        },
    )
    async def get_character_blueprint_concept(
        self, *, concept: CharacterConcept
    ) -> CharacterConcept:
        """Get a character concept by ID."""
        return concept

    @get(
        path=urls.CharacterBlueprints.VAMPIRE_CLANS,
        summary="List vampire clans",
        operation_id="listCharacterBlueprintVampireClans",
        description="Retrieve all vampire clans.",
        cache=True,
        return_dto=dto.VampireClanDTO,
    )
    async def list_character_blueprint_vampire_clans(
        self,
        *,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        game_version: Annotated[
            GameVersion | None,
            Parameter(
                description="Show vampire clans for this game version.", title="Game Version"
            ),
        ] = None,
    ) -> OffsetPagination[VampireClan]:
        """List all vampire clans."""
        filters = [
            VampireClan.is_archived == False,
        ]
        if game_version:
            filters.append(VampireClan.game_versions == game_version)

        count = await VampireClan.find(*filters).count()
        vampire_clans = (
            await VampireClan.find(*filters).skip(offset).limit(limit).sort("name").to_list()
        )
        return OffsetPagination(items=vampire_clans, limit=limit, offset=offset, total=count)

    @get(
        path=urls.CharacterBlueprints.VAMPIRE_CLAN_DETAIL,
        summary="Get vampire clan",
        operation_id="getCharacterBlueprintVampireClan",
        description="Retrieve a specific vampire clan including its name, description, and examples.",
        cache=True,
        return_dto=dto.VampireClanDTO,
        dependencies={
            "vampire_clan": Provide(deps.provide_vampire_clan_by_id),
        },
    )
    async def get_character_blueprint_vampire_clan(
        self, *, vampire_clan: VampireClan
    ) -> VampireClan:
        """Get a vampire clan by ID."""
        return vampire_clan

    @get(
        path=urls.CharacterBlueprints.WEREWOLF_TRIBES,
        summary="List werewolf tribes",
        operation_id="listCharacterBlueprintWerewolfTribes",
        description="Retrieve all werewolf tribes.",
        cache=True,
        return_dto=dto.WerewolfTribeDTO,
    )
    async def list_character_blueprint_werewolf_tribes(
        self,
        *,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        game_version: Annotated[
            GameVersion | None,
            Parameter(
                description="Show werewolf tribes for this game version.", title="Game Version"
            ),
        ] = None,
    ) -> OffsetPagination[WerewolfTribe]:
        """List all werewolf tribes."""
        filters = [
            WerewolfTribe.is_archived == False,
        ]
        if game_version:
            filters.append(WerewolfTribe.game_versions == game_version)

        count = await WerewolfTribe.find(*filters).count()
        werewolf_tribes = (
            await WerewolfTribe.find(*filters).skip(offset).limit(limit).sort("name").to_list()
        )
        return OffsetPagination(items=werewolf_tribes, limit=limit, offset=offset, total=count)

    @get(
        path=urls.CharacterBlueprints.WEREWOLF_TRIBE_DETAIL,
        summary="Get werewolf tribe",
        operation_id="getCharacterBlueprintWerewolfTribe",
        description="Retrieve a specific werewolf tribe including its name, description, and examples.",
        cache=True,
        return_dto=dto.WerewolfTribeDTO,
        dependencies={
            "werewolf_tribe": Provide(deps.provide_werewolf_tribe_by_id),
        },
    )
    async def get_character_blueprint_werewolf_tribe(
        self, *, werewolf_tribe: WerewolfTribe
    ) -> WerewolfTribe:
        """Get a werewolf tribe by ID."""
        return werewolf_tribe

    @get(
        path=urls.CharacterBlueprints.WEREWOLF_AUSPICES,
        summary="List werewolf auspices",
        operation_id="listCharacterBlueprintWerewolfAuspices",
        description="Retrieve all werewolf auspices.",
        cache=True,
        return_dto=dto.WerewolfAuspiceDTO,
    )
    async def list_character_blueprint_werewolf_auspices(
        self,
        *,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        game_version: Annotated[
            GameVersion | None,
            Parameter(
                description="Show werewolf auspices for this game version.", title="Game Version"
            ),
        ] = None,
    ) -> OffsetPagination[WerewolfAuspice]:
        """List all werewolf auspices."""
        filters = [
            WerewolfAuspice.is_archived == False,
        ]
        if game_version:
            filters.append(WerewolfAuspice.game_versions == game_version)

        count = await WerewolfAuspice.find(*filters).count()
        werewolf_auspices = (
            await WerewolfAuspice.find(*filters).skip(offset).limit(limit).sort("name").to_list()
        )
        return OffsetPagination(items=werewolf_auspices, limit=limit, offset=offset, total=count)

    @get(
        path=urls.CharacterBlueprints.WEREWOLF_AUSPIE_DETAIL,
        summary="Get werewolf auspice",
        operation_id="getCharacterBlueprintWerewolfAuspice",
        description="Retrieve a specific werewolf auspice including its name, description, and examples.",
        cache=True,
        return_dto=dto.WerewolfAuspiceDTO,
        dependencies={
            "werewolf_auspice": Provide(deps.provide_werewolf_auspice_by_id),
        },
    )
    async def get_character_blueprint_werewolf_auspice(
        self, *, werewolf_auspice: WerewolfAuspice
    ) -> WerewolfAuspice:
        """Get a werewolf auspice by ID."""
        return werewolf_auspice

    @get(
        path=urls.CharacterBlueprints.WEREWOLF_GIFTS,
        summary="List werewolf gifts",
        operation_id="listCharacterBlueprintWerewolfGifts",
        description="Retrieve all werewolf gifts.",
        cache=True,
        return_dto=dto.WerewolfGiftDTO,
    )
    async def list_character_blueprint_werewolf_gifts(
        self,
        *,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        tribe_id: Annotated[
            PydanticObjectId | None,
            Parameter(description="Show werewolf gifts for this tribe.", title="Tribe ID"),
        ] = None,
        auspice_id: Annotated[
            PydanticObjectId | None,
            Parameter(description="Show werewolf gifts for this auspice.", title="Auspice ID"),
        ] = None,
        game_version: Annotated[
            GameVersion | None,
            Parameter(
                description="Show werewolf gifts for this game version.", title="Game Version"
            ),
        ] = None,
    ) -> OffsetPagination[WerewolfGift]:
        """List all werewolf gifts."""
        filters = [
            WerewolfGift.is_archived == False,
        ]
        if tribe_id:
            filters.append(WerewolfGift.tribe_id == tribe_id)
        if auspice_id:
            filters.append(WerewolfGift.auspice_id == auspice_id)
        if game_version:
            filters.append(WerewolfGift.game_versions == game_version)

        count = await WerewolfGift.find(*filters).count()
        werewolf_gifts = (
            await WerewolfGift.find(*filters).skip(offset).limit(limit).sort("name").to_list()
        )
        return OffsetPagination(items=werewolf_gifts, limit=limit, offset=offset, total=count)

    @get(
        path=urls.CharacterBlueprints.WEREWOLF_GIFT_DETAIL,
        summary="Get werewolf gift",
        operation_id="getCharacterBlueprintWerewolfGift",
        description="Retrieve a specific werewolf gift including its name, description, and examples.",
        cache=True,
        return_dto=dto.WerewolfGiftDTO,
        dependencies={
            "werewolf_gift": Provide(deps.provide_werewolf_gift_by_id),
        },
    )
    async def get_character_blueprint_werewolf_gift(
        self, *, werewolf_gift: WerewolfGift
    ) -> WerewolfGift:
        """Get a werewolf gift by ID."""
        return werewolf_gift

    @get(
        path=urls.CharacterBlueprints.WEREWOLF_RITES,
        summary="List werewolf rites",
        operation_id="listCharacterBlueprintWerewolfRites",
        description="Retrieve all werewolf rites.",
        cache=True,
        return_dto=dto.WerewolfRiteDTO,
    )
    async def list_character_blueprint_werewolf_rites(
        self,
        *,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[WerewolfRite]:
        """List all werewolf rites."""
        filters = [
            WerewolfRite.is_archived == False,
        ]

        count = await WerewolfRite.find(*filters).count()
        werewolf_rites = (
            await WerewolfRite.find(*filters).skip(offset).limit(limit).sort("name").to_list()
        )
        return OffsetPagination(items=werewolf_rites, limit=limit, offset=offset, total=count)

    @get(
        path=urls.CharacterBlueprints.WEREWOLF_RITE_DETAIL,
        summary="Get werewolf rite",
        operation_id="getCharacterBlueprintWerewolfRite",
        description="Retrieve a specific werewolf rite including its name, description, and examples.",
        cache=True,
        return_dto=dto.WerewolfRiteDTO,
        dependencies={
            "werewolf_rite": Provide(deps.provide_werewolf_rite_by_id),
        },
    )
    async def get_character_blueprint_werewolf_rite(
        self, *, werewolf_rite: WerewolfRite
    ) -> WerewolfRite:
        """Get a werewolf rite by ID."""
        return werewolf_rite

    @get(
        path=urls.CharacterBlueprints.HUNTER_EDGES,
        summary="List hunter edges",
        operation_id="listCharacterBlueprintHunterEdges",
        description="Retrieve all hunter edges.",
        cache=True,
        return_dto=dto.HunterEdgeDTO,
    )
    async def list_character_blueprint_hunter_edges(
        self,
        *,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        edge_type: Annotated[
            HunterEdgeType | None,
            Parameter(description="Show hunter edges for this type.", title="Hunter Edge Type"),
        ] = None,
    ) -> OffsetPagination[HunterEdge]:
        """List all hunter edges."""
        filters = [
            HunterEdge.is_archived == False,
        ]
        if edge_type:
            filters.append(HunterEdge.type == edge_type)

        count = await HunterEdge.find(*filters).count()
        hunter_edges = (
            await HunterEdge.find(*filters).skip(offset).limit(limit).sort("name").to_list()
        )
        return OffsetPagination(items=hunter_edges, limit=limit, offset=offset, total=count)

    @get(
        path=urls.CharacterBlueprints.HUNTER_EDGE_DETAIL,
        summary="Get hunter edge",
        operation_id="getCharacterBlueprintHunterEdge",
        description="Retrieve a specific hunter edge including its name, description, and examples.",
        cache=True,
        return_dto=dto.HunterEdgeDTO,
        dependencies={
            "hunter_edge": Provide(deps.provide_hunter_edge_by_id),
        },
    )
    async def get_character_blueprint_hunter_edge(self, *, hunter_edge: HunterEdge) -> HunterEdge:
        """Get a hunter edge by ID."""
        return hunter_edge

    @get(
        path=urls.CharacterBlueprints.HUNTER_EDGE_PERKS,
        summary="List hunter edge perks",
        operation_id="listCharacterBlueprintHunterEdgePerks",
        description="Retrieve all hunter edge perks.",
        cache=True,
        return_dto=dto.HunterEdgePerkDTO,
        dependencies={
            "hunter_edge": Provide(deps.provide_hunter_edge_by_id),
        },
    )
    async def list_character_blueprint_hunter_edge_perks(
        self,
        *,
        hunter_edge: HunterEdge,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
    ) -> OffsetPagination[HunterEdgePerk]:
        """List all hunter edge perks."""
        filters = [
            HunterEdgePerk.is_archived == False,
            HunterEdgePerk.edge_id == hunter_edge.id,
        ]

        count = await HunterEdgePerk.find(*filters).count()
        hunter_edge_perks = (
            await HunterEdgePerk.find(*filters).skip(offset).limit(limit).sort("name").to_list()
        )

        return OffsetPagination(items=hunter_edge_perks, limit=limit, offset=offset, total=count)

    @get(
        path=urls.CharacterBlueprints.HUNTER_EDGE_PERK_DETAIL,
        summary="Get hunter edge perk",
        operation_id="getCharacterBlueprintHunterEdgePerk",
        description="Retrieve a specific hunter edge perk including its name, description, and examples.",
        cache=True,
        return_dto=dto.HunterEdgePerkDTO,
        dependencies={
            "hunter_edge": Provide(deps.provide_hunter_edge_by_id),
            "hunter_edge_perk": Provide(deps.provide_hunter_edge_perk_by_id),
        },
    )
    async def get_character_blueprint_hunter_edge_perk(
        self, *, hunter_edge_perk: HunterEdgePerk
    ) -> HunterEdgePerk:
        """Get a hunter edge perk by ID."""
        return hunter_edge_perk
