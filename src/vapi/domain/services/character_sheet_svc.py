"""Service for building the full character sheet."""

from __future__ import annotations

from asyncio import gather
from typing import TYPE_CHECKING

from beanie import PydanticObjectId  # noqa: TC002
from beanie.operators import In

from vapi.constants import CharacterClass
from vapi.db.models import (
    CharacterTrait,
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)
from vapi.domain.controllers.character.dto import (
    CharacterFullSheetDTO,
    FullSheetCharacterTraitDTO,
    FullSheetTraitCategoryDTO,
    FullSheetTraitSectionDTO,
    FullSheetTraitSubcategoryDTO,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable

    from vapi.db.models import Character


class CharacterSheetService:
    """Build the hierarchical full character sheet.

    Assembles sections > categories > subcategories > traits from the
    database skeleton and the character's actual traits.
    """

    async def get_character_full_sheet(
        self, character: Character, *, include_available_traits: bool = False
    ) -> CharacterFullSheetDTO:
        """Build the hierarchical full character sheet (sections > categories > subcategories > traits).

        The sheet skeleton includes all sections, categories, and subcategories that match the
        character's class and game version, even if the character has no traits in them. Traits the
        character actually has are then slotted into that skeleton.

        A storyteller may grant traits outside a character's class/version (e.g. a vampire discipline
        on a mortal). To handle this, we fetch the class/version skeleton and the character's traits
        in parallel, then merge any additional parent structures referenced by out-of-class traits.
        This avoids an extra DB round-trip for the common case while still capturing edge-case traits.
        """
        # Fetch the sheet skeleton for this character's class/version and the character's actual
        # traits in parallel. Both queries are independent so we can run them concurrently.
        coros = [
            CharSheetSection.find(
                CharSheetSection.is_archived == False,
                CharSheetSection.character_classes == character.character_class,
                CharSheetSection.game_versions == character.game_version,
            )
            .sort("order")
            .to_list(),
            TraitCategory.find(
                TraitCategory.is_archived == False,
                TraitCategory.character_classes == character.character_class,
                TraitCategory.game_versions == character.game_version,
            )
            .sort("order")
            .to_list(),
            TraitSubcategory.find(
                TraitSubcategory.is_archived == False,
                TraitSubcategory.character_classes == character.character_class,
                TraitSubcategory.game_versions == character.game_version,
            )
            .sort("name")
            .to_list(),
            CharacterTrait.find(
                CharacterTrait.character_id == character.id,
                fetch_links=True,
            ).to_list(),
        ]
        if include_available_traits:
            coros.append(
                Trait.find(
                    Trait.is_archived == False,
                    Trait.character_classes == character.character_class,
                    Trait.game_versions == character.game_version,
                    Trait.is_custom == False,
                )
                .sort("name")
                .to_list()
            )

        results = await gather(*coros)

        skeleton_sections: list[CharSheetSection] = results[0]
        skeleton_categories: list[TraitCategory] = results[1]
        skeleton_subcategories: list[TraitSubcategory] = results[2]
        all_character_traits: list[CharacterTrait] = results[3]
        all_available_traits: list[Trait] = results[4] if include_available_traits else []

        # Index skeleton results by ID for deduplication when merging trait-referenced structures
        skeleton_section_ids: set[PydanticObjectId] = {
            s.id for s in skeleton_sections if s.id is not None
        }
        skeleton_category_ids: set[PydanticObjectId] = {
            c.id for c in skeleton_categories if c.id is not None
        }
        skeleton_subcategory_ids: set[PydanticObjectId] = {
            s.id for s in skeleton_subcategories if s.id is not None
        }

        # Index traits by their parent subcategory/category for O(1) lookups during assembly
        traits_by_subcategory: dict[PydanticObjectId, list[CharacterTrait]] = {}
        traits_by_category_no_sub: dict[PydanticObjectId, list[CharacterTrait]] = {}

        # Track IDs of structures referenced by traits that fall outside the character's
        # class/version skeleton (e.g. a vampire discipline granted to a mortal by a storyteller)
        missing_section_ids: set[PydanticObjectId] = set()
        missing_category_ids: set[PydanticObjectId] = set()
        missing_subcategory_ids: set[PydanticObjectId] = set()

        for ct in all_character_traits:
            trait: Trait = ct.trait  # type: ignore[assignment]

            if trait.sheet_section_id not in skeleton_section_ids:
                missing_section_ids.add(trait.sheet_section_id)
            if trait.parent_category_id not in skeleton_category_ids:
                missing_category_ids.add(trait.parent_category_id)
            if (
                trait.trait_subcategory_id
                and trait.trait_subcategory_id not in skeleton_subcategory_ids
            ):
                missing_subcategory_ids.add(trait.trait_subcategory_id)

            if trait.trait_subcategory_id:
                traits_by_subcategory.setdefault(trait.trait_subcategory_id, []).append(ct)
            else:
                traits_by_category_no_sub.setdefault(trait.parent_category_id, []).append(ct)

        # Backfill any structures referenced by out-of-class/version traits
        await self._backfill_missing_structures(
            skeleton_sections,
            skeleton_categories,
            skeleton_subcategories,
            missing_section_ids,
            missing_category_ids,
            missing_subcategory_ids,
        )

        filtered_available_traits = self._filter_available_traits(character, all_available_traits)

        available_by_subcategory, available_by_category_no_sub = self._index_available_traits(
            filtered_available_traits, all_character_traits
        )

        sections = self._assemble_sheet_sections(
            sections_objects=skeleton_sections,
            categories_objects=skeleton_categories,
            subcategories_objects=skeleton_subcategories,
            traits_by_subcategory=traits_by_subcategory,
            traits_by_category_no_sub=traits_by_category_no_sub,
            available_by_subcategory=available_by_subcategory,
            available_by_category_no_sub=available_by_category_no_sub,
        )

        return CharacterFullSheetDTO(character=character, sections=sections)

    async def get_character_full_sheet_category(
        self,
        character: Character,
        category: TraitCategory,
        *,
        include_available_traits: bool = False,
    ) -> FullSheetTraitCategoryDTO:
        """Build a single category slice of the character's full sheet.

        Fetch only the subcategories and traits for one category, enabling efficient
        UI refreshes after a trait edit without rebuilding the entire sheet hierarchy.

        Subcategories are fetched without class/version filtering so that out-of-class
        traits (e.g. storyteller grants) are naturally included when the client requests
        a specific category.

        Args:
            character: The character whose traits to include.
            category: The trait category to build.
            include_available_traits: If True, include standard traits the character
                could add but hasn't yet.
        """
        coros: list[Awaitable[list]] = [
            TraitSubcategory.find(
                TraitSubcategory.is_archived == False,
                TraitSubcategory.parent_category_id == category.id,
            )
            .sort("name")
            .to_list(),
            CharacterTrait.find(
                CharacterTrait.character_id == character.id,
                fetch_links=True,
            ).to_list(),
        ]

        if include_available_traits:
            coros.append(
                Trait.find(
                    Trait.is_archived == False,
                    Trait.parent_category_id == category.id,
                    Trait.is_custom == False,
                )
                .sort("name")
                .to_list()
            )

        results = await gather(*coros)
        subcategories: list[TraitSubcategory] = results[0]
        all_character_traits: list[CharacterTrait] = results[1]
        all_available_traits: list[Trait] = results[2] if include_available_traits else []

        # Filter character traits to those belonging to this category
        subcategory_ids: set[PydanticObjectId] = {s.id for s in subcategories if s.id is not None}
        traits_by_subcategory: dict[PydanticObjectId, list[CharacterTrait]] = {}
        category_traits_no_sub: list[CharacterTrait] = []

        for ct in all_character_traits:
            trait: Trait = ct.trait  # type: ignore[assignment]
            if trait.trait_subcategory_id and trait.trait_subcategory_id in subcategory_ids:
                traits_by_subcategory.setdefault(trait.trait_subcategory_id, []).append(ct)
            elif trait.parent_category_id == category.id and not trait.trait_subcategory_id:
                category_traits_no_sub.append(ct)

        filtered_available_traits = self._filter_available_traits(character, all_available_traits)

        available_by_subcategory, available_by_category_no_sub = self._index_available_traits(
            filtered_available_traits, all_character_traits
        )

        return FullSheetTraitCategoryDTO(
            id=category.id,
            name=category.name,
            description=category.description,
            order=category.order,
            show_when_empty=category.show_when_empty,
            initial_cost=category.initial_cost,
            upgrade_cost=category.upgrade_cost,
            subcategories=[
                self._build_subcategory_dto(sub, traits_by_subcategory, available_by_subcategory)
                for sub in subcategories
            ],
            character_traits=[self._build_trait_dto(ct) for ct in category_traits_no_sub],
            available_traits=available_by_category_no_sub.get(category.id, []),
        )

    @staticmethod
    async def _backfill_missing_structures(
        skeleton_sections: list[CharSheetSection],
        skeleton_categories: list[TraitCategory],
        skeleton_subcategories: list[TraitSubcategory],
        missing_section_ids: set[PydanticObjectId],
        missing_category_ids: set[PydanticObjectId],
        missing_subcategory_ids: set[PydanticObjectId],
    ) -> None:
        """Fetch and merge sheet structures referenced by out-of-class/version traits.

        A storyteller may grant traits outside a character's class/version (e.g. a vampire
        discipline on a mortal). This method fetches the parent sections, categories, and
        subcategories for those traits and merges them into the skeleton lists in-place.

        Args:
            skeleton_sections: The sections list to extend (mutated in-place).
            skeleton_categories: The categories list to extend (mutated in-place).
            skeleton_subcategories: The subcategories list to extend (mutated in-place).
            missing_section_ids: Section IDs referenced by traits but absent from the skeleton.
            missing_category_ids: Category IDs referenced by traits but absent from the skeleton.
            missing_subcategory_ids: Subcategory IDs referenced by traits but absent from the skeleton.
        """
        if not (missing_section_ids or missing_category_ids or missing_subcategory_ids):
            return

        # Build only the queries we actually need rather than using no-op placeholders
        targets: list[tuple[list, set[PydanticObjectId]]] = [
            (skeleton_sections, missing_section_ids),
            (skeleton_categories, missing_category_ids),
            (skeleton_subcategories, missing_subcategory_ids),
        ]
        models = [CharSheetSection, TraitCategory, TraitSubcategory]

        coros = []
        active_targets: list[list[CharSheetSection | TraitCategory | TraitSubcategory]] = []
        for (target_list, id_set), model in zip(targets, models, strict=True):
            if id_set:
                coros.append(model.find(model.is_archived == False, In(model.id, id_set)).to_list())
                active_targets.append(target_list)

        results = await gather(*coros)
        for target_list, extra in zip(active_targets, results, strict=True):
            target_list.extend(extra)

        # Re-sort after merging to maintain consistent ordering
        skeleton_sections.sort(key=lambda s: s.order)
        skeleton_categories.sort(key=lambda c: c.order)
        skeleton_subcategories.sort(key=lambda s: s.name)

    @staticmethod
    def _build_trait_dto(ct: CharacterTrait) -> FullSheetCharacterTraitDTO:
        """Convert a CharacterTrait into the full-sheet DTO representation."""
        return FullSheetCharacterTraitDTO(
            trait=ct.trait,  # type: ignore[arg-type]
            value=ct.value,
            id=ct.id,
            character_id=ct.character_id,
        )

    @staticmethod
    def _build_subcategory_dto(
        sub: TraitSubcategory,
        traits_by_subcategory: dict[PydanticObjectId, list[CharacterTrait]],
        available_by_subcategory: dict[PydanticObjectId, list[Trait]],
    ) -> FullSheetTraitSubcategoryDTO:
        """Build a single subcategory DTO with its character and available traits."""
        return FullSheetTraitSubcategoryDTO(
            id=sub.id,
            name=sub.name,
            description=sub.description,
            show_when_empty=sub.show_when_empty,
            initial_cost=sub.initial_cost,
            upgrade_cost=sub.upgrade_cost,
            requires_parent=sub.requires_parent,
            pool=sub.pool,
            system=sub.system,
            hunter_edge_type=sub.hunter_edge_type,
            character_traits=[
                CharacterSheetService._build_trait_dto(ct)
                for ct in traits_by_subcategory.get(sub.id, [])
            ],
            available_traits=available_by_subcategory.get(sub.id, []),
        )

    @staticmethod
    def _index_available_traits(
        all_available_traits: list[Trait],
        all_character_traits: list[CharacterTrait],
    ) -> tuple[dict[PydanticObjectId, list[Trait]], dict[PydanticObjectId, list[Trait]]]:
        """Index available traits by subcategory/category, excluding already-assigned traits.

        Returns:
            A tuple of (available_by_subcategory, available_by_category_no_sub).
        """
        assigned_trait_ids: set[PydanticObjectId] = {ct.trait.id for ct in all_character_traits}  # type: ignore[attr-defined]
        available_by_subcategory: dict[PydanticObjectId, list[Trait]] = {}
        available_by_category_no_sub: dict[PydanticObjectId, list[Trait]] = {}

        for avail_trait in all_available_traits:
            if avail_trait.id in assigned_trait_ids:
                continue
            if avail_trait.trait_subcategory_id:
                available_by_subcategory.setdefault(avail_trait.trait_subcategory_id, []).append(
                    avail_trait
                )
            else:
                available_by_category_no_sub.setdefault(avail_trait.parent_category_id, []).append(
                    avail_trait
                )

        return available_by_subcategory, available_by_category_no_sub

    @staticmethod
    def _filter_available_traits(
        character: Character, available_traits: list[Trait]
    ) -> list[Trait]:
        """Filter available traits based on character-specific eligibility.

        For werewolves, restrict gift traits to those matching the character's tribe,
        auspice, or marked as native (available to all werewolves). Non-gift traits
        (merits, flaws, rites, etc.) pass through unfiltered.

        Args:
            character: The character to filter traits for.
            available_traits: The full list of available traits to filter.
        """
        if character.character_class is not CharacterClass.WEREWOLF:
            return available_traits

        tribe_id = character.werewolf_attributes.tribe_id if character.werewolf_attributes else None
        auspice_id = (
            character.werewolf_attributes.auspice_id if character.werewolf_attributes else None
        )

        return [
            t
            for t in available_traits
            if t.gift_attributes is None
            or t.gift_attributes.is_native_gift
            or (tribe_id and t.gift_attributes.tribe_id == tribe_id)
            or (auspice_id and t.gift_attributes.auspice_id == auspice_id)
        ]

    @staticmethod
    def _assemble_sheet_sections(
        *,
        sections_objects: list[CharSheetSection],
        categories_objects: list[TraitCategory],
        subcategories_objects: list[TraitSubcategory],
        traits_by_subcategory: dict[PydanticObjectId, list[CharacterTrait]],
        traits_by_category_no_sub: dict[PydanticObjectId, list[CharacterTrait]],
        available_by_subcategory: dict[PydanticObjectId, list[Trait]],
        available_by_category_no_sub: dict[PydanticObjectId, list[Trait]],
    ) -> list[FullSheetTraitSectionDTO]:
        """Assemble the nested section > category > subcategory > trait DTO hierarchy.

        Args:
            sections_objects: All sheet sections to include.
            categories_objects: All trait categories to include.
            subcategories_objects: All trait subcategories to include.
            traits_by_subcategory: Character traits indexed by subcategory ID.
            traits_by_category_no_sub: Character traits indexed by category ID (no subcategory).
            available_by_subcategory: Available traits indexed by subcategory ID.
            available_by_category_no_sub: Available traits indexed by category ID (no subcategory).

        Returns:
            list[FullSheetTraitSectionDTO]: The assembled section hierarchy.
        """
        # Pre-index subcategories by parent category
        subcategories_by_category: dict[PydanticObjectId, list[TraitSubcategory]] = {}
        for subcategory in subcategories_objects:
            if subcategory.parent_category_id:
                subcategories_by_category.setdefault(subcategory.parent_category_id, []).append(
                    subcategory
                )

        # Pre-index categories by parent section
        categories_by_section: dict[PydanticObjectId, list[TraitCategory]] = {}
        for category in categories_objects:
            categories_by_section.setdefault(category.parent_sheet_section_id, []).append(category)

        return [
            FullSheetTraitSectionDTO(
                id=section.id,
                name=section.name,
                description=section.description,
                order=section.order,
                show_when_empty=section.show_when_empty,
                categories=[
                    FullSheetTraitCategoryDTO(
                        id=category.id,
                        name=category.name,
                        description=category.description,
                        order=category.order,
                        show_when_empty=category.show_when_empty,
                        initial_cost=category.initial_cost,
                        upgrade_cost=category.upgrade_cost,
                        subcategories=[
                            CharacterSheetService._build_subcategory_dto(
                                sub, traits_by_subcategory, available_by_subcategory
                            )
                            for sub in subcategories_by_category.get(category.id, [])
                        ],
                        character_traits=[
                            CharacterSheetService._build_trait_dto(ct)
                            for ct in traits_by_category_no_sub.get(category.id, [])
                        ],
                        available_traits=available_by_category_no_sub.get(category.id, []),
                    )
                    for category in categories_by_section.get(section.id, [])
                ],
            )
            for section in sections_objects
        ]
