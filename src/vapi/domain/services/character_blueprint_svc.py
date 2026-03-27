"""Character blueprint service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vapi.constants import BlueprintTraitOrderBy
from vapi.db.models import CharSheetSection, Trait, TraitCategory, TraitSubcategory

if TYPE_CHECKING:
    from beanie import PydanticObjectId

    from vapi.constants import CharacterClass, GameVersion


class CharacterBlueprintService:
    """Character blueprint service."""

    async def list_sheet_sections(
        self,
        *,
        game_version: GameVersion | None = None,
        character_class: CharacterClass | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[int, list[CharSheetSection]]:
        """List all character blueprint sections.

        Args:
            game_version: Filter sections by game version.
            character_class: Filter sections by character class.
            limit: The limit of sections to return.
            offset: The offset of the sections to return.

        Returns:
            A tuple containing the total number of sections and the list of sections.
        """
        filters = [
            CharSheetSection.is_archived == False,
        ]
        if game_version:
            filters.append(CharSheetSection.game_versions == game_version)
        if character_class:
            filters.append(CharSheetSection.character_classes == character_class)

        count = await CharSheetSection.find(*filters).count()
        sections = (
            await CharSheetSection.find(*filters).sort("order").skip(offset).limit(limit).to_list()
        )

        return count, sections

    async def list_sheet_categories(
        self,
        *,
        game_version: GameVersion | None = None,
        section_id: PydanticObjectId | None = None,
        character_class: CharacterClass | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[int, list[TraitCategory]]:
        """List all character blueprint categories.

        Args:
            game_version: Filter categories by game version.
            section_id: Filter categories by parent sheet section.
            character_class: Filter categories by character class.
            limit: The limit of categories to return.
            offset: The offset of the categories to return.

        Returns:
            A tuple containing the total number of categories and the list of categories.
        """
        filters = [
            TraitCategory.is_archived == False,
        ]
        if game_version:
            filters.append(TraitCategory.game_versions == game_version)
        if section_id:
            filters.append(TraitCategory.parent_sheet_section_id == section_id)
        if character_class:
            filters.append(TraitCategory.character_classes == character_class)

        count = await TraitCategory.find(*filters).count()
        categories = (
            await TraitCategory.find(*filters).sort("order").skip(offset).limit(limit).to_list()
        )
        return count, categories

    async def list_sheet_category_subcategories(
        self,
        *,
        game_version: GameVersion | None = None,
        category_id: PydanticObjectId | None = None,
        character_class: CharacterClass | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[int, list[TraitSubcategory]]:
        """List all character blueprint subcategories.

        Args:
            game_version: Filter subcategories by game version.
            category_id: Filter subcategories by parent category.
            character_class: Filter subcategories by character class.
            limit: The limit of subcategories to return.
            offset: The offset of the subcategories to return.

        Returns:
            A tuple containing the total number of subcategories and the list of subcategories.
        """
        filters = [
            TraitSubcategory.is_archived == False,
        ]
        if game_version:
            filters.append(TraitSubcategory.game_versions == game_version)
        if category_id:
            filters.append(TraitSubcategory.parent_category_id == category_id)
        if character_class:
            filters.append(TraitSubcategory.character_classes == character_class)

        count = await TraitSubcategory.find(*filters).count()
        subcategories = (
            await TraitSubcategory.find(*filters).sort("name").skip(offset).limit(limit).to_list()
        )
        return count, subcategories

    async def list_all_traits(  # noqa: C901, PLR0912, PLR0913
        self,
        *,
        game_version: GameVersion | None = None,
        character_class: CharacterClass | None = None,
        parent_category_id: PydanticObjectId | None = None,
        subcategory_id: PydanticObjectId | None = None,
        exclude_subcategory_traits: bool = False,
        is_rollable: bool | None = None,
        order_by: BlueprintTraitOrderBy = BlueprintTraitOrderBy.NAME,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[int, list[Trait]]:
        """List all character blueprint traits.

        Args:
            game_version: The game version to list the traits for.
            character_class: The character class to list the traits for.
            parent_category_id: The parent category id to list the traits for.
            subcategory_id: Filter traits by subcategory.
            exclude_subcategory_traits: When True, only return traits without a subcategory.
            is_rollable: Whether to list the rollable traits.
            order_by: The order by to list the traits for.
            limit: The limit of traits to return.
            offset: The offset of the traits to return.

        Returns:
            A tuple containing the total number of traits and the list of traits.
        """
        filters = [
            Trait.is_archived == False,
            Trait.custom_for_character_id == None,
        ]
        if game_version:
            filters.append(Trait.game_versions == game_version)
        if character_class:
            filters.append(Trait.character_classes == character_class)
        if parent_category_id:
            filters.append(Trait.parent_category_id == parent_category_id)
        if subcategory_id:
            filters.append(Trait.trait_subcategory_id == subcategory_id)
        if exclude_subcategory_traits:
            filters.append(Trait.trait_subcategory_id == None)
        if is_rollable is not None:
            filters.append(Trait.is_rollable == is_rollable)

        count = await Trait.find(*filters).count()

        if order_by == BlueprintTraitOrderBy.NAME:
            traits = await Trait.find(*filters).skip(offset).limit(limit).sort("name").to_list()
        elif order_by == BlueprintTraitOrderBy.SHEET:
            # Build match conditions for aggregation pipeline
            match_conditions: dict = {"is_archived": False, "custom_for_character_id": None}
            if game_version:
                match_conditions["game_versions"] = game_version.value
            if character_class:
                match_conditions["character_classes"] = character_class.value
            if parent_category_id:
                match_conditions["parent_category_id"] = parent_category_id
            if subcategory_id:
                match_conditions["trait_subcategory_id"] = subcategory_id
            if exclude_subcategory_traits:
                match_conditions["trait_subcategory_id"] = None
            if is_rollable is not None:
                match_conditions["is_rollable"] = is_rollable

            # Aggregation pipeline to sort by CharSheetSection.order, TraitCategory.order, Trait.name
            pipeline = [
                {"$match": match_conditions},
                {
                    "$lookup": {
                        "from": "CharSheetSection",
                        "localField": "sheet_section_id",
                        "foreignField": "_id",
                        "as": "_section",
                    }
                },
                {"$unwind": {"path": "$_section", "preserveNullAndEmptyArrays": True}},
                {
                    "$lookup": {
                        "from": "TraitCategory",
                        "localField": "parent_category_id",
                        "foreignField": "_id",
                        "as": "_category",
                    }
                },
                {"$unwind": {"path": "$_category", "preserveNullAndEmptyArrays": True}},
                {
                    "$sort": {
                        "_section.order": 1,
                        "_category.order": 1,
                        "name": 1,
                    }
                },
                {"$skip": offset},
                {"$limit": limit},
                {"$project": {"_section": 0, "_category": 0}},
            ]

            results = await Trait.aggregate(pipeline).to_list()
            traits = [Trait.model_validate(doc) for doc in results]

        return count, traits
