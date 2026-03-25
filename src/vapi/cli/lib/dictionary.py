"""Dictionary term synchronization service."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vapi.db.models import (
    DictionaryTerm,
    Trait,
    TraitSubcategory,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)

if TYPE_CHECKING:
    from beanie import PydanticObjectId

    from vapi.db.models.constants.trait import GiftAttributes

logger = logging.getLogger("vapi")


class DictionaryService:
    """Build and sync global dictionary terms from database entities."""

    def __init__(self) -> None:
        self.created: int = 0
        self.updated: int = 0
        self._tribes: list[WerewolfTribe] = []
        self._auspices: list[WerewolfAuspice] = []
        self._tribes_by_id: dict[PydanticObjectId, str] = {}
        self._auspices_by_id: dict[PydanticObjectId, str] = {}

    @property
    def total(self) -> int:
        """Derive total from created + updated counts."""
        return self.created + self.updated

    async def sync_all(self) -> None:
        """Build dictionary terms for all entity types, then log counts."""
        # Build lookup maps for gift attribute name resolution and reuse for term sync
        self._tribes = await WerewolfTribe.find().to_list()
        self._auspices = await WerewolfAuspice.find().to_list()
        self._tribes_by_id = {t.id: t.name for t in self._tribes}
        self._auspices_by_id = {a.id: a.name for a in self._auspices}

        await self._sync_vampire_clan_terms()
        await self._sync_werewolf_auspice_terms()
        await self._sync_werewolf_tribe_terms()
        await self._sync_subcategory_terms()
        await self._sync_trait_terms()
        self._log_counts()

    async def _upsert_term(
        self, term: str, *, definition: str | None = None, link: str | None = None
    ) -> None:
        """Create or update a global dictionary term.

        Args:
            term: The term string to upsert.
            definition: Optional markdown definition text.
            link: Optional URL link for the term.
        """
        if not definition and not link:
            return

        existing_term = await DictionaryTerm.find_one(
            DictionaryTerm.term == term.lower().strip(), DictionaryTerm.is_global == True
        )
        if not existing_term:
            await DictionaryTerm(
                term=term.lower().strip(),
                definition=definition.strip() if definition else None,
                link=link.strip() if link else None,
                is_global=True,
            ).insert()
            self.created += 1
        elif existing_term.definition != definition or existing_term.link != link:
            existing_term.definition = definition.strip() if definition else None
            existing_term.link = link.strip() if link else None
            await existing_term.save()
            self.updated += 1

    def _build_gift_attributes_definition(
        self,
        gift_attributes: GiftAttributes,
        *,
        tribe_name: str | None = None,
        auspice_name: str | None = None,
    ) -> str:
        """Build the gift attributes portion of a trait definition.

        Args:
            gift_attributes: The gift attributes to format.
            tribe_name: Resolved tribe name from the lookup map.
            auspice_name: Resolved auspice name from the lookup map.

        Returns:
            str: Formatted gift attributes string.
        """
        cost_string = f"  - Cost: `{gift_attributes.cost}`\n" if gift_attributes.cost else ""
        duration_string = (
            f"  - Duration: `{gift_attributes.duration}`\n" if gift_attributes.duration else ""
        )
        minimum_renown_string = (
            f"  - Minimum Renown: `{gift_attributes.minimum_renown}`\n"
            if gift_attributes.minimum_renown
            else ""
        )
        tribe_string = f"  - Tribe: `{tribe_name}`\n" if tribe_name else ""
        auspice_string = f"  - Auspice: `{auspice_name}`\n" if auspice_name else ""

        result = "\n- Gift Attributes:\n"
        result += f"  - Renown: `{gift_attributes.renown.value.title()}`\n"
        result += cost_string
        result += duration_string
        result += minimum_renown_string
        result += tribe_string
        result += auspice_string
        return result

    def _build_trait_definition(self, trait: Trait) -> str | None:
        """Build a dictionary definition string for a trait.

        Combine the trait's description, details, gift attributes, system, pool, and opposing pool
        into a formatted definition suitable for a global dictionary term.

        Args:
            trait: The trait to build a definition for.

        Returns:
            str | None: The formatted definition, or None if the trait has no description.
        """
        if not trait.description:
            return None

        section_string = (
            f"`{trait.sheet_section_name.title()}` > `{trait.parent_category_name.title()}`"
        )
        if trait.trait_subcategory_name:
            section_string += f" > `{trait.trait_subcategory_name.title()}`"

        pool_string = f"\n- Pool: `{trait.pool or '-'}`" if trait.pool else ""
        opposing_pool_string = (
            f"\n- Opposing Pool: `{trait.opposing_pool.title()}`" if trait.opposing_pool else ""
        )
        system_string = f"\n- System: `{trait.system or '-'}`" if trait.system else ""

        definition = f"""\
{trait.description}

### Trait Details:
- Sheet Section: {section_string}
- Character Classes: `{"`, `".join(c.title() for c in trait.character_classes)}`
- Game Versions: `{"`, `".join(v.title() for v in trait.game_versions)}`{pool_string}{opposing_pool_string}{system_string}"""

        if trait.gift_attributes:
            tribe_name = (
                self._tribes_by_id.get(trait.gift_attributes.tribe_id)
                if trait.gift_attributes.tribe_id
                else None
            )
            auspice_name = (
                self._auspices_by_id.get(trait.gift_attributes.auspice_id)
                if trait.gift_attributes.auspice_id
                else None
            )
            definition += self._build_gift_attributes_definition(
                trait.gift_attributes, tribe_name=tribe_name, auspice_name=auspice_name
            )

        return definition

    async def _sync_vampire_clan_terms(self) -> None:
        """Create dictionary terms for all vampire clans."""
        clans = await VampireClan.find().to_list()
        for clan in clans:
            await self._upsert_term(clan.name, definition=clan.description, link=clan.link)

    async def _sync_werewolf_auspice_terms(self) -> None:
        """Create dictionary terms for all werewolf auspices."""
        for auspice in self._auspices:
            await self._upsert_term(auspice.name, definition=auspice.description, link=auspice.link)

    async def _sync_werewolf_tribe_terms(self) -> None:
        """Create dictionary terms for all werewolf tribes."""
        for tribe in self._tribes:
            await self._upsert_term(tribe.name, definition=tribe.description, link=tribe.link)

    async def _sync_subcategory_terms(self) -> None:
        """Create dictionary terms for trait subcategories with descriptions."""
        subcategories = await TraitSubcategory.find().to_list()
        for subcategory in subcategories:
            if subcategory.description or subcategory.system or subcategory.pool:
                desc = subcategory.description or ""
                if subcategory.system:
                    desc += "\n## System:\n" + subcategory.system
                if subcategory.pool:
                    desc += "\n## Pool:\n" + subcategory.pool
                await self._upsert_term(subcategory.name, definition=desc)

    async def _sync_trait_terms(self) -> None:
        """Create dictionary terms for all non-archived traits."""
        traits = await Trait.find(Trait.is_archived == False).to_list()
        for trait in traits:
            definition = self._build_trait_definition(trait)
            if definition or trait.link:
                await self._upsert_term(trait.name, definition=definition, link=trait.link)

    def _log_counts(self) -> None:
        """Log dictionary term sync counts."""
        logger.info(
            "Dictionary terms",
            extra={
                "num_created": self.created,
                "num_updated": self.updated,
                "num_total": self.total,
                "component": "cli",
                "command": "bootstrap",
            },
        )
