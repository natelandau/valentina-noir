"""Character blueprint service."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tortoise.expressions import Q

from vapi.constants import BlueprintTraitOrderBy
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import (
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)

if TYPE_CHECKING:
    from uuid import UUID

    from tortoise.models import Model
    from tortoise.queryset import QuerySet

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
        qs = self._build_queryset(
            CharSheetSection,
            game_version=game_version,
            character_class=character_class,
        )
        return await self._paginated_query(qs, order_by="order", limit=limit, offset=offset)

    async def list_sheet_categories(
        self,
        *,
        game_version: GameVersion | None = None,
        section_id: UUID | None = None,
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
        qs = self._build_queryset(
            TraitCategory,
            game_version=game_version,
            character_class=character_class,
        )
        if section_id:
            qs = qs.filter(sheet_section_id=section_id)

        return await self._paginated_query(
            qs, order_by="order", limit=limit, offset=offset, prefetch=["sheet_section"]
        )

    async def list_sheet_category_subcategories(
        self,
        *,
        game_version: GameVersion | None = None,
        category_id: UUID | None = None,
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
        qs = self._build_queryset(
            TraitSubcategory,
            game_version=game_version,
            character_class=character_class,
        )
        if category_id:
            qs = qs.filter(category_id=category_id)

        return await self._paginated_query(
            qs, order_by="name", limit=limit, offset=offset, prefetch=["category", "sheet_section"]
        )

    async def list_all_traits(  # noqa: PLR0913
        self,
        *,
        game_version: GameVersion | None = None,
        character_class: CharacterClass | None = None,
        category_id: UUID | None = None,
        subcategory_id: UUID | None = None,
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
            category_id: The category id to list the traits for.
            subcategory_id: Filter traits by subcategory.
            exclude_subcategory_traits: When True, only return traits without a subcategory.
            is_rollable: Whether to list the rollable traits.
            order_by: The order by to list the traits for.
            limit: The limit of traits to return.
            offset: The offset of the traits to return.

        Returns:
            A tuple containing the total number of traits and the list of traits.
        """
        qs = self._build_queryset(
            Trait,
            game_version=game_version,
            character_class=character_class,
            extra_q=Q(custom_for_character_id=None),
        )
        if category_id:
            qs = qs.filter(category_id=category_id)
        if subcategory_id:
            qs = qs.filter(subcategory_id=subcategory_id)
        if exclude_subcategory_traits:
            qs = qs.filter(subcategory_id=None)
        if is_rollable is not None:
            qs = qs.filter(is_rollable=is_rollable)

        sort_key: str | tuple[str, ...] = "name"
        if order_by == BlueprintTraitOrderBy.SHEET:
            sort_key = ("sheet_section__order", "category__order", "name")

        prefetch = ["category", "sheet_section", "subcategory", "gift_tribe", "gift_auspice"]

        return await self._paginated_query(
            qs, order_by=sort_key, limit=limit, offset=offset, prefetch=prefetch
        )

    async def list_concepts(
        self,
        *,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[int, list[CharacterConcept]]:
        """List all non-archived character concepts.

        Company-scoped filtering will be added when the Company model migrates to PostgreSQL.

        Args:
            limit: The limit of concepts to return.
            offset: The offset of the concepts to return.

        Returns:
            A tuple containing the total number of concepts and the list of concepts.
        """
        qs = CharacterConcept.filter(is_archived=False)
        return await self._paginated_query(qs, order_by="name", limit=limit, offset=offset)

    async def list_vampire_clans(
        self,
        *,
        game_version: GameVersion | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[int, list[VampireClan]]:
        """List all vampire clans.

        Args:
            game_version: Filter clans by game version.
            limit: The limit of clans to return.
            offset: The offset of the clans to return.

        Returns:
            A tuple containing the total number of clans and the list of clans.
        """
        qs = self._build_queryset(VampireClan, game_version=game_version)
        return await self._paginated_query(
            qs, order_by="name", limit=limit, offset=offset, prefetch=["disciplines"]
        )

    async def list_werewolf_tribes(
        self,
        *,
        game_version: GameVersion | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[int, list[WerewolfTribe]]:
        """List all werewolf tribes.

        Args:
            game_version: Filter tribes by game version.
            limit: The limit of tribes to return.
            offset: The offset of the tribes to return.

        Returns:
            A tuple containing the total number of tribes and the list of tribes.
        """
        qs = self._build_queryset(WerewolfTribe, game_version=game_version)
        return await self._paginated_query(
            qs, order_by="name", limit=limit, offset=offset, prefetch=["gifts"]
        )

    async def list_werewolf_auspices(
        self,
        *,
        game_version: GameVersion | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> tuple[int, list[WerewolfAuspice]]:
        """List all werewolf auspices.

        Args:
            game_version: Filter auspices by game version.
            limit: The limit of auspices to return.
            offset: The offset of the auspices to return.

        Returns:
            A tuple containing the total number of auspices and the list of auspices.
        """
        qs = self._build_queryset(WerewolfAuspice, game_version=game_version)
        return await self._paginated_query(
            qs, order_by="name", limit=limit, offset=offset, prefetch=["gifts"]
        )

    @staticmethod
    def _build_queryset(
        model: type[Model],
        *,
        game_version: GameVersion | None = None,
        character_class: CharacterClass | None = None,
        extra_q: Q | None = None,
    ) -> QuerySet:
        """Build a base queryset with common filters.

        Args:
            model: The Tortoise model to query.
            game_version: Filter by game version.
            character_class: Filter by character class.
            extra_q: Additional Q filter to apply.

        Returns:
            A filtered QuerySet.
        """
        qs = model.filter(is_archived=False)
        if extra_q:
            qs = qs.filter(extra_q)
        if game_version:
            qs = qs.filter(game_versions__contains=[game_version.value])
        if character_class:
            qs = qs.filter(character_classes__contains=[character_class.value])
        return qs

    @staticmethod
    async def _paginated_query(
        qs: QuerySet,
        *,
        order_by: str | tuple[str, ...],
        limit: int,
        offset: int,
        prefetch: list[str] | None = None,
    ) -> tuple[int, list]:
        """Run a count and paginated fetch concurrently.

        Args:
            qs: The base QuerySet to paginate.
            order_by: Field name(s) to sort by. A tuple applies multi-column ordering.
            limit: Maximum number of results.
            offset: Number of results to skip.
            prefetch: Relations to prefetch on the results.

        Returns:
            A tuple of (total_count, page_of_results).
        """
        if isinstance(order_by, tuple):
            fetch_qs = qs.order_by(*order_by).offset(offset).limit(limit)
        else:
            fetch_qs = qs.order_by(order_by).offset(offset).limit(limit)
        if prefetch:
            fetch_qs = fetch_qs.prefetch_related(*prefetch)

        count, items = await asyncio.gather(qs.count(), fetch_qs)
        return count, list(items)
