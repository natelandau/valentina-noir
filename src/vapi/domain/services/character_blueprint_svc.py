"""Character blueprint service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from beanie.operators import Or

from vapi.db.models import CharSheetSection, Trait, TraitCategory
from vapi.domain.controllers.character_blueprint.schemas import TraitSort

if TYPE_CHECKING:
    from beanie import PydanticObjectId

    from vapi.constants import CharacterClass, GameVersion


class CharacterBlueprintService:
    """Character blueprint service."""

    async def list_sheet_sections(
        self,
        *,
        game_version: GameVersion,
        character_class: CharacterClass | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[int, list[CharSheetSection]]:
        """List all character blueprint sections.

        Args:
            game_version: The game version to list the sections for.
            character_class: The character class to list the sections for.
            limit: The limit of sections to return.
            offset: The offset of the sections to return.

        Returns:
            A tuple containing the total number of sections and the list of sections.
        """
        filters = [
            CharSheetSection.is_archived == False,
            CharSheetSection.game_versions == game_version,
        ]
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
        game_version: GameVersion,
        section: CharSheetSection,
        character_class: CharacterClass | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[int, list[TraitCategory]]:
        """List all character blueprint categories.

        Args:
            game_version: The game version to list the categories for.
            section: The section to list the categories for.
            character_class: The character class to list the categories for.
            limit: The limit of categories to return.
            offset: The offset of the categories to return.

        Returns:
            A tuple containing the total number of categories and the list of categories.
        """
        filters = [
            TraitCategory.is_archived == False,
            TraitCategory.game_versions == game_version,
            TraitCategory.parent_sheet_section_id == section.id,
        ]
        if character_class:
            filters.append(TraitCategory.character_classes == character_class)

        count = await TraitCategory.find(*filters).count()
        categories = (
            await TraitCategory.find(*filters).sort("order").skip(offset).limit(limit).to_list()
        )
        return count, categories

    async def list_sheet_category_traits(
        self,
        *,
        game_version: GameVersion,
        category: TraitCategory,
        character_class: CharacterClass | None = None,
        character_id: PydanticObjectId | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[int, list[Trait]]:
        """List all character blueprint category traits.

        Args:
            game_version: The game version to list the traits for.
            category: The category to list the traits for.
            character_class: The character class to list the traits for.
            character_id: Include custom traits assigned to this character.
            limit: The limit of traits to return.
            offset: The offset of the traits to return.

        Returns:
            A tuple containing the total number of traits and the list of traits.
        """
        filters = [
            Trait.is_archived == False,
            Trait.parent_category_id == category.id,
            Trait.game_versions == game_version,
        ]
        if character_class:
            filters.append(Trait.character_classes == character_class)

        if character_id:
            filters.append(
                Or(  # type: ignore [arg-type]
                    Trait.custom_for_character_id == character_id,
                    Trait.custom_for_character_id == None,
                )
            )
        else:
            filters.append(Trait.custom_for_character_id == None)

        count = await Trait.find(*filters).count()
        traits = (
            await Trait.find(*filters)
            .sort("parent_category_id")
            .sort("order")
            .skip(offset)
            .limit(limit)
            .to_list()
        )
        return count, traits

    async def list_all_traits(
        self,
        *,
        game_version: GameVersion | None = None,
        character_class: CharacterClass | None = None,
        parent_category_id: PydanticObjectId | None = None,
        order_by: TraitSort = TraitSort.NAME,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[int, list[Trait]]:
        """List all character blueprint traits.

        Args:
            game_version: The game version to list the traits for.
            character_class: The character class to list the traits for.
            parent_category_id: The parent category id to list the traits for.
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

        count = await Trait.find(*filters).count()

        if order_by == TraitSort.NAME:
            traits = await Trait.find(*filters).skip(offset).limit(limit).sort("name").to_list()
        elif order_by == TraitSort.SHEET:
            # Build match conditions for aggregation pipeline
            match_conditions: dict = {"is_archived": False, "custom_for_character_id": None}
            if game_version:
                match_conditions["game_versions"] = game_version.value
            if character_class:
                match_conditions["character_classes"] = character_class.value
            if parent_category_id:
                match_conditions["parent_category_id"] = parent_category_id

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
