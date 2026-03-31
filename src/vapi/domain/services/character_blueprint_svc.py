"""Character blueprint service."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from vapi.constants import BlueprintTraitOrderBy
from vapi.db.models import CharSheetSection, Trait, TraitCategory, TraitSubcategory

if TYPE_CHECKING:
    from beanie import Document, PydanticObjectId

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
        filters = self._common_filters(
            CharSheetSection,
            game_version=game_version,
            character_class=character_class,
        )
        return await self._paginated_query(
            CharSheetSection, filters, sort_key="order", limit=limit, offset=offset
        )

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
        filters = self._common_filters(
            TraitCategory,
            game_version=game_version,
            character_class=character_class,
        )
        if section_id:
            filters.append(TraitCategory.parent_sheet_section_id == section_id)

        return await self._paginated_query(
            TraitCategory, filters, sort_key="order", limit=limit, offset=offset
        )

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
        filters = self._common_filters(
            TraitSubcategory,
            game_version=game_version,
            character_class=character_class,
        )
        if category_id:
            filters.append(TraitSubcategory.parent_category_id == category_id)

        return await self._paginated_query(
            TraitSubcategory, filters, sort_key="name", limit=limit, offset=offset
        )

    async def list_all_traits(  # noqa: PLR0913
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
        filters = self._common_filters(
            Trait,
            game_version=game_version,
            character_class=character_class,
            extra=[Trait.custom_for_character_id == None],
        )
        if parent_category_id:
            filters.append(Trait.parent_category_id == parent_category_id)
        if subcategory_id:
            filters.append(Trait.trait_subcategory_id == subcategory_id)
        if exclude_subcategory_traits:
            filters.append(Trait.trait_subcategory_id == None)
        if is_rollable is not None:
            filters.append(Trait.is_rollable == is_rollable)

        if order_by == BlueprintTraitOrderBy.NAME:
            return await self._paginated_query(
                Trait, filters, sort_key="name", limit=limit, offset=offset
            )

        # SHEET ordering requires an aggregation pipeline to join and sort by
        # CharSheetSection.order, TraitCategory.order, then Trait.name
        count = await Trait.find(*filters).count()
        match_conditions = Trait.find(*filters).get_filter_query()

        pipeline: list[dict[str, Any]] = [
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

    @staticmethod
    def _common_filters(
        model: type[Document],
        *,
        game_version: GameVersion | None = None,
        character_class: CharacterClass | None = None,
        extra: list[Any] | None = None,
    ) -> list[Any]:
        """Build the common filter list shared by all list methods.

        Args:
            model: The Beanie document model to filter.
            game_version: Filter by game version.
            character_class: Filter by character class.
            extra: Additional base filters to include.

        Returns:
            list: The filter expressions for use with ``model.find()``.
        """
        filters: list[Any] = [model.is_archived == False]
        if extra:
            filters.extend(extra)
        if game_version:
            filters.append(model.game_versions == game_version)
        if character_class:
            filters.append(model.character_classes == character_class)
        return filters

    @staticmethod
    async def _paginated_query(
        model: type[Document],
        filters: list[Any],
        *,
        sort_key: str,
        limit: int,
        offset: int,
    ) -> tuple[int, list[Any]]:
        """Run a count and paginated fetch concurrently.

        Args:
            model: The Beanie document model to query.
            filters: Filter expressions for ``model.find()``.
            sort_key: Field name to sort by.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            A tuple of (total_count, page_of_documents).
        """
        count, items = await asyncio.gather(
            model.find(*filters).count(),
            model.find(*filters).sort(sort_key).skip(offset).limit(limit).to_list(),
        )
        return count, items
