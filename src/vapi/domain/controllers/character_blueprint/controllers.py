"""Character blueprint controllers."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from beanie.operators import Or
from litestar.controller import Controller
from litestar.di import Provide
from litestar.handlers import get
from litestar.params import Parameter

from vapi.constants import (
    BlueprintTraitOrderBy,
    CharacterClass,
    GameVersion,
)
from vapi.db.models import (
    CharacterConcept,
    CharSheetSection,
    Company,
    Trait,
    TraitCategory,
    TraitSubcategory,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)
from vapi.domain import deps, urls
from vapi.domain.paginator import OffsetPagination
from vapi.domain.services import CharacterBlueprintService
from vapi.lib.guards import developer_company_user_guard
from vapi.openapi.tags import APITags

from . import docs, dto


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
        description=docs.LIST_SECTIONS_DESCRIPTION,
        cache=True,
        return_dto=dto.CharacterSheetDTO,
    )
    async def list_character_blueprint_sections(
        self,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        game_version: Annotated[
            GameVersion | None,
            Parameter(description="Filter sections by game version.", title="Game Version"),
        ] = None,
        character_class: Annotated[
            CharacterClass | None,
            Parameter(
                description="Filter sections by character class.",
                title="Character Class",
            ),
        ] = None,
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
        description=docs.GET_SECTION_DESCRIPTION,
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

    ## CATEGORIES #######################################################
    @get(
        path=urls.CharacterBlueprints.CATEGORIES,
        summary="List trait categories",
        operation_id="listCharacterBlueprintCategories",
        description=docs.LIST_CATEGORIES_DESCRIPTION,
        cache=True,
        return_dto=dto.TraitCategoryDTO,
    )
    async def list_character_blueprint_categories(
        self,
        *,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        game_version: Annotated[
            GameVersion | None,
            Parameter(description="Filter categories by game version.", title="Game Version"),
        ] = None,
        section_id: Annotated[
            PydanticObjectId | None,
            Parameter(
                description="Filter categories by parent sheet section.",
                title="Section ID",
            ),
        ] = None,
        character_class: Annotated[
            CharacterClass | None,
            Parameter(
                description="Filter categories by character class.",
                title="Character Class",
            ),
        ] = None,
    ) -> OffsetPagination[TraitCategory]:
        """List all character blueprint categories."""
        service = CharacterBlueprintService()
        count, categories = await service.list_sheet_categories(
            game_version=game_version,
            section_id=section_id,
            character_class=character_class,
            limit=limit,
            offset=offset,
        )
        return OffsetPagination(items=categories, limit=limit, offset=offset, total=count)

    @get(
        path=urls.CharacterBlueprints.CATEGORY_DETAIL,
        summary="Get trait category",
        operation_id="getCharacterBlueprintCategory",
        description=docs.GET_CATEGORY_DESCRIPTION,
        cache=True,
        return_dto=dto.TraitCategoryDTO,
        dependencies={
            "category": Provide(deps.provide_trait_category_by_id),
        },
    )
    async def get_character_blueprint_category(self, *, category: TraitCategory) -> TraitCategory:
        """Get a character sheet category by ID."""
        return category

    ## SUBCATEGORIES #######################################################
    @get(
        path=urls.CharacterBlueprints.SUBCATEGORIES,
        summary="List subcategories",
        operation_id="listCharacterBlueprintSubcategories",
        description=docs.LIST_SUBCATEGORIES_DESCRIPTION,
        cache=True,
        return_dto=dto.TraitSubcategoryDTO,
    )
    async def list_character_blueprint_subcategories(
        self,
        *,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        game_version: Annotated[
            GameVersion | None,
            Parameter(description="Filter subcategories by game version.", title="Game Version"),
        ] = None,
        category_id: Annotated[
            PydanticObjectId | None,
            Parameter(
                description="Filter subcategories by parent category.",
                title="Category ID",
            ),
        ] = None,
        character_class: Annotated[
            CharacterClass | None,
            Parameter(
                description="Filter subcategories by character class.",
                title="Character Class",
            ),
        ] = None,
    ) -> OffsetPagination[TraitSubcategory]:
        """List all character blueprint subcategories."""
        service = CharacterBlueprintService()
        count, subcategories = await service.list_sheet_category_subcategories(
            game_version=game_version,
            category_id=category_id,
            character_class=character_class,
            limit=limit,
            offset=offset,
        )
        return OffsetPagination(items=subcategories, limit=limit, offset=offset, total=count)

    @get(
        path=urls.CharacterBlueprints.SUBCATEGORY_DETAIL,
        summary="Get subcategory",
        operation_id="getCharacterBlueprintSubcategory",
        description=docs.GET_SUBCATEGORY_DESCRIPTION,
        cache=True,
        return_dto=dto.TraitSubcategoryDTO,
        dependencies={
            "subcategory": Provide(deps.provide_trait_subcategory_by_id),
        },
    )
    async def get_character_blueprint_subcategory(
        self, *, subcategory: TraitSubcategory
    ) -> TraitSubcategory:
        """Get a character blueprint subcategory by ID."""
        return subcategory

    ## ALL TRAITS #######################################################
    @get(
        path=urls.CharacterBlueprints.TRAITS,
        summary="List all traits",
        operation_id="listAllCharacterBlueprintTraits",
        description=docs.LIST_ALL_TRAITS_DESCRIPTION,
        cache=True,
        return_dto=dto.TraitDTO,
    )
    async def list_all_traits(  # noqa: PLR0913
        self,
        *,
        limit: Annotated[int, Parameter(ge=0, le=100)] = 10,
        offset: Annotated[int, Parameter(ge=0)] = 0,
        game_version: Annotated[
            GameVersion | None,
            Parameter(description="Filter traits by game version.", title="Game Version"),
        ] = None,
        character_class: Annotated[
            CharacterClass | None,
            Parameter(description="Filter traits by character class.", title="Character Class"),
        ] = None,
        parent_category_id: Annotated[
            PydanticObjectId | None,
            Parameter(description="Filter traits by category.", title="Category ID"),
        ] = None,
        subcategory_id: Annotated[
            PydanticObjectId | None,
            Parameter(description="Filter traits by subcategory.", title="Subcategory ID"),
        ] = None,
        exclude_subcategory_traits: Annotated[
            bool,
            Parameter(description="Exclude traits that belong to a subcategory."),
        ] = False,
        is_rollable: Annotated[
            bool | None, Parameter(description="Filter by rollable status.")
        ] = None,
        order_by: Annotated[
            BlueprintTraitOrderBy,
            Parameter(description="Sort traits by this field.", title="Sort"),
        ] = BlueprintTraitOrderBy.NAME,
    ) -> OffsetPagination[Trait]:
        """List all constant character traits."""
        service = CharacterBlueprintService()
        count, traits = await service.list_all_traits(
            game_version=game_version,
            character_class=character_class,
            parent_category_id=parent_category_id,
            subcategory_id=subcategory_id,
            exclude_subcategory_traits=exclude_subcategory_traits,
            is_rollable=is_rollable,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return OffsetPagination(items=traits, limit=limit, offset=offset, total=count)

    @get(
        path=urls.CharacterBlueprints.TRAIT_DETAIL,
        summary="Get trait",
        operation_id="getCharacterBlueprintTrait",
        description=docs.GET_TRAIT_DESCRIPTION,
        cache=True,
        return_dto=dto.TraitDTO,
        dependencies={
            "trait": Provide(deps.provide_trait_by_id),
        },
    )
    async def get_trait(self, *, trait: Trait) -> Trait:
        """Get a character sheet trait by ID."""
        return trait

    ## Classes, Concepts, and class specific options ############################################

    @get(
        path=urls.CharacterBlueprints.CONCEPTS,
        summary="List concepts",
        operation_id="listCharacterBlueprintConcepts",
        description=docs.LIST_CONCEPTS_DESCRIPTION,
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
        description=docs.GET_CONCEPT_DESCRIPTION,
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
        description=docs.LIST_VAMPIRE_CLANS_DESCRIPTION,
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
        description=docs.GET_VAMPIRE_CLAN_DESCRIPTION,
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
        description=docs.LIST_WEREWOLF_TRIBES_DESCRIPTION,
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
        description=docs.GET_WEREWOLF_TRIBE_DESCRIPTION,
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
        description=docs.LIST_WEREWOLF_AUSPICES_DESCRIPTION,
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
        path=urls.CharacterBlueprints.WEREWOLF_AUSPICE_DETAIL,
        summary="Get werewolf auspice",
        operation_id="getCharacterBlueprintWerewolfAuspice",
        description=docs.GET_WEREWOLF_AUSPICE_DESCRIPTION,
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
