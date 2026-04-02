"""Service for building the full character sheet."""

from asyncio import gather
from typing import TYPE_CHECKING
from uuid import UUID

from vapi.constants import CharacterClass
from vapi.db.sql_models.character import CharacterTrait
from vapi.db.sql_models.character_sheet import (
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)

if TYPE_CHECKING:
    from vapi.db.sql_models.character import Character
    from vapi.domain.controllers.character.dto import (
        CharacterFullSheetDTO,
        FullSheetTraitCategoryDTO,
        FullSheetTraitSectionDTO,
    )


class CharacterSheetService:
    """Build the hierarchical full character sheet.

    Assembles sections > categories > subcategories > traits from the
    database skeleton and the character's actual traits.
    """

    async def get_character_full_sheet(
        self, character: "Character", *, include_available_traits: bool = False
    ) -> "CharacterFullSheetDTO":
        """Build the hierarchical full character sheet (sections > categories > subcategories > traits).

        The sheet skeleton includes all sections, categories, and subcategories that match the
        character's class and game version, even if the character has no traits in them. Traits the
        character actually has are then slotted into that skeleton.

        A storyteller may grant traits outside a character's class/version (e.g. a vampire discipline
        on a mortal). To handle this, we fetch the class/version skeleton and the character's traits
        in parallel, then merge any additional parent structures referenced by out-of-class traits.
        This avoids an extra DB round-trip for the common case while still capturing edge-case traits.
        """
        from vapi.domain.controllers.character.dto import CharacterFullSheetDTO

        char_class = character.character_class
        game_ver = character.game_version

        coros: list = [
            CharSheetSection.filter(
                is_archived=False,
                character_classes__contains=[char_class],
                game_versions__contains=[game_ver],
            ).order_by("order"),
            TraitCategory.filter(
                is_archived=False,
                character_classes__contains=[char_class],
                game_versions__contains=[game_ver],
            ).order_by("order"),
            TraitSubcategory.filter(
                is_archived=False,
                character_classes__contains=[char_class],
                game_versions__contains=[game_ver],
            ).order_by("name"),
            CharacterTrait.filter(character_id=character.id).prefetch_related(
                "trait", "trait__category", "trait__subcategory", "trait__sheet_section"
            ),
        ]
        if include_available_traits:
            coros.append(
                Trait.filter(
                    is_archived=False,
                    character_classes__contains=[char_class],
                    game_versions__contains=[game_ver],
                    is_custom=False,
                )
                .prefetch_related(
                    "category", "sheet_section", "subcategory", "gift_tribe", "gift_auspice"
                )
                .order_by("name")
            )

        results = await gather(*coros)

        skeleton_sections: list[CharSheetSection] = list(results[0])
        skeleton_categories: list[TraitCategory] = list(results[1])
        skeleton_subcategories: list[TraitSubcategory] = list(results[2])
        all_character_traits: list[CharacterTrait] = list(results[3])
        all_available_traits: list[Trait] = list(results[4]) if include_available_traits else []

        # Index skeleton results by ID for deduplication when merging trait-referenced structures
        skeleton_section_ids: set[UUID] = {s.id for s in skeleton_sections}
        skeleton_category_ids: set[UUID] = {c.id for c in skeleton_categories}
        skeleton_subcategory_ids: set[UUID] = {s.id for s in skeleton_subcategories}

        # Index traits by their parent subcategory/category for O(1) lookups during assembly
        traits_by_subcategory: dict[UUID, list[CharacterTrait]] = {}
        traits_by_category_no_sub: dict[UUID, list[CharacterTrait]] = {}

        # Track IDs of structures referenced by traits that fall outside the character's
        # class/version skeleton (e.g. a vampire discipline granted to a mortal by a storyteller)
        missing_section_ids: set[UUID] = set()
        missing_category_ids: set[UUID] = set()
        missing_subcategory_ids: set[UUID] = set()

        for ct in all_character_traits:
            trait: Trait = ct.trait

            if trait.sheet_section_id not in skeleton_section_ids:  # type: ignore[attr-defined]
                missing_section_ids.add(trait.sheet_section_id)  # type: ignore[attr-defined]
            if trait.category_id not in skeleton_category_ids:  # type: ignore[attr-defined]
                missing_category_ids.add(trait.category_id)  # type: ignore[attr-defined]
            if trait.subcategory_id and trait.subcategory_id not in skeleton_subcategory_ids:  # type: ignore[attr-defined]
                missing_subcategory_ids.add(trait.subcategory_id)  # type: ignore[attr-defined]

            if trait.subcategory_id:  # type: ignore[attr-defined]
                traits_by_subcategory.setdefault(trait.subcategory_id, []).append(ct)  # type: ignore[attr-defined]
            else:
                traits_by_category_no_sub.setdefault(trait.category_id, []).append(ct)  # type: ignore[attr-defined]

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

        return CharacterFullSheetDTO.build(character=character, sections=sections)

    async def get_character_full_sheet_category(
        self,
        character: "Character",
        category: TraitCategory,
        *,
        include_available_traits: bool = False,
    ) -> "FullSheetTraitCategoryDTO":
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
        from vapi.domain.controllers.character.dto import FullSheetTraitCategoryDTO

        coros: list = [
            TraitSubcategory.filter(
                is_archived=False,
                category_id=category.id,
            ).order_by("name"),
            CharacterTrait.filter(character_id=character.id).prefetch_related(
                "trait", "trait__category", "trait__subcategory", "trait__sheet_section"
            ),
        ]

        if include_available_traits:
            coros.append(
                Trait.filter(
                    is_archived=False,
                    category_id=category.id,
                    is_custom=False,
                )
                .prefetch_related(
                    "category", "sheet_section", "subcategory", "gift_tribe", "gift_auspice"
                )
                .order_by("name")
            )

        results = await gather(*coros)
        subcategories: list[TraitSubcategory] = list(results[0])
        all_character_traits: list[CharacterTrait] = list(results[1])
        all_available_traits: list[Trait] = list(results[2]) if include_available_traits else []

        # Filter character traits to those belonging to this category
        subcategory_ids: set[UUID] = {s.id for s in subcategories}
        traits_by_subcategory: dict[UUID, list[CharacterTrait]] = {}
        category_traits_no_sub: list[CharacterTrait] = []

        for ct in all_character_traits:
            trait: Trait = ct.trait
            if trait.subcategory_id and trait.subcategory_id in subcategory_ids:  # type: ignore[attr-defined]
                traits_by_subcategory.setdefault(trait.subcategory_id, []).append(ct)  # type: ignore[attr-defined]
            elif trait.category_id == category.id and not trait.subcategory_id:  # type: ignore[attr-defined]
                category_traits_no_sub.append(ct)

        filtered_available_traits = self._filter_available_traits(character, all_available_traits)

        available_by_subcategory, available_by_category_no_sub = self._index_available_traits(
            filtered_available_traits, all_character_traits
        )

        return FullSheetTraitCategoryDTO.build(
            category=category,
            subcategories=subcategories,
            traits_by_subcategory=traits_by_subcategory,
            category_traits_no_sub=category_traits_no_sub,
            available_by_subcategory=available_by_subcategory,
            available_by_category_no_sub=available_by_category_no_sub,
        )

    @staticmethod
    async def _backfill_missing_structures(
        skeleton_sections: list[CharSheetSection],
        skeleton_categories: list[TraitCategory],
        skeleton_subcategories: list[TraitSubcategory],
        missing_section_ids: set[UUID],
        missing_category_ids: set[UUID],
        missing_subcategory_ids: set[UUID],
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
        targets: list[tuple[list, set[UUID]]] = [
            (skeleton_sections, missing_section_ids),
            (skeleton_categories, missing_category_ids),
            (skeleton_subcategories, missing_subcategory_ids),
        ]
        models = [CharSheetSection, TraitCategory, TraitSubcategory]

        coros = []
        active_targets: list[list] = []
        for (target_list, id_set), model in zip(targets, models, strict=True):
            if id_set:
                coros.append(model.filter(is_archived=False, id__in=id_set))
                active_targets.append(target_list)

        results = await gather(*coros)
        for target_list, extra in zip(active_targets, results, strict=True):
            target_list.extend(extra)

        # Re-sort after merging to maintain consistent ordering
        skeleton_sections.sort(key=lambda s: s.order)
        skeleton_categories.sort(key=lambda c: c.order)
        skeleton_subcategories.sort(key=lambda s: s.name)

    @staticmethod
    def _index_available_traits(
        all_available_traits: list[Trait],
        all_character_traits: list[CharacterTrait],
    ) -> tuple[dict[UUID, list[Trait]], dict[UUID, list[Trait]]]:
        """Index available traits by subcategory/category, excluding already-assigned traits.

        Returns:
            A tuple of (available_by_subcategory, available_by_category_no_sub).
        """
        assigned_trait_ids: set[UUID] = {ct.trait.id for ct in all_character_traits}
        available_by_subcategory: dict[UUID, list[Trait]] = {}
        available_by_category_no_sub: dict[UUID, list[Trait]] = {}

        for avail_trait in all_available_traits:
            if avail_trait.id in assigned_trait_ids:
                continue
            sub_id: UUID | None = avail_trait.subcategory_id  # type: ignore[attr-defined]
            cat_id: UUID = avail_trait.category_id  # type: ignore[attr-defined]
            if sub_id:
                available_by_subcategory.setdefault(sub_id, []).append(avail_trait)
            else:
                available_by_category_no_sub.setdefault(cat_id, []).append(avail_trait)

        return available_by_subcategory, available_by_category_no_sub

    @staticmethod
    def _filter_available_traits(
        character: "Character", available_traits: list[Trait]
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

        tribe_id: UUID | None = None
        auspice_id: UUID | None = None
        try:
            werewolf_attrs = character.werewolf_attributes
            if werewolf_attrs:
                tribe_id = werewolf_attrs.tribe_id  # type: ignore[attr-defined]
                auspice_id = werewolf_attrs.auspice_id  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 S110
            pass

        return [
            t
            for t in available_traits
            if (not t.gift_is_native and not t.gift_tribe_id and not t.gift_auspice_id)  # type: ignore[attr-defined]
            or t.gift_is_native
            or (tribe_id and t.gift_tribe_id == tribe_id)  # type: ignore[attr-defined]
            or (auspice_id and t.gift_auspice_id == auspice_id)  # type: ignore[attr-defined]
        ]

    @staticmethod
    def _assemble_sheet_sections(
        *,
        sections_objects: list[CharSheetSection],
        categories_objects: list[TraitCategory],
        subcategories_objects: list[TraitSubcategory],
        traits_by_subcategory: dict[UUID, list[CharacterTrait]],
        traits_by_category_no_sub: dict[UUID, list[CharacterTrait]],
        available_by_subcategory: dict[UUID, list[Trait]],
        available_by_category_no_sub: dict[UUID, list[Trait]],
    ) -> list["FullSheetTraitSectionDTO"]:
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
        from vapi.domain.controllers.character.dto import (
            FullSheetCharacterTraitDTO,
            FullSheetTraitCategoryDTO,
            FullSheetTraitSectionDTO,
            FullSheetTraitSubcategoryDTO,
        )
        from vapi.domain.controllers.character_blueprint.dto import TraitResponse

        # Pre-index subcategories by parent category
        subcategories_by_category: dict[UUID, list[TraitSubcategory]] = {}
        for subcategory in subcategories_objects:
            cat_id: UUID = subcategory.category_id  # type: ignore[attr-defined]
            subcategories_by_category.setdefault(cat_id, []).append(subcategory)

        # Pre-index categories by parent section
        categories_by_section: dict[UUID, list[TraitCategory]] = {}
        for category in categories_objects:
            sec_id: UUID = category.sheet_section_id  # type: ignore[attr-defined]
            categories_by_section.setdefault(sec_id, []).append(category)

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
                            FullSheetTraitSubcategoryDTO.build(
                                subcategory=sub,
                                character_traits=traits_by_subcategory.get(sub.id, []),
                                available_traits=available_by_subcategory.get(sub.id, []),
                            )
                            for sub in subcategories_by_category.get(category.id, [])
                        ],
                        character_traits=[
                            FullSheetCharacterTraitDTO.from_model(ct)
                            for ct in traits_by_category_no_sub.get(category.id, [])
                        ],
                        available_traits=[
                            TraitResponse.from_model(t)
                            for t in available_by_category_no_sub.get(category.id, [])
                        ],
                    )
                    for category in categories_by_section.get(section.id, [])
                ],
            )
            for section in sections_objects
        ]
