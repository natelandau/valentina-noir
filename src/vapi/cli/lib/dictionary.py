"""Dictionary term synchronization service."""

from __future__ import annotations  # noqa: I001

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

from vapi.constants import DictionarySourceType

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
        self._existing_terms: dict[str, DictionaryTerm] = {}

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

        # Bulk-fetch all existing global terms to avoid N+1 find_one queries in _upsert_term
        all_terms = await DictionaryTerm.find(DictionaryTerm.source_type != None).to_list()
        self._existing_terms = {t.term: t for t in all_terms}

        await self._sync_vampire_clan_terms()
        await self._sync_werewolf_auspice_terms()
        await self._sync_werewolf_tribe_terms()
        await self._sync_subcategory_terms()
        await self._sync_trait_terms()
        self._log_counts()

    async def _upsert_term(
        self,
        term: str,
        *,
        definition: str | None = None,
        link: str | None = None,
        source_type: DictionarySourceType,
        source_id: PydanticObjectId,
    ) -> None:
        """Create or update a global dictionary term.

        Args:
            term: The term string to upsert.
            definition: Optional markdown definition text.
            link: Optional URL link for the term.
            source_type: The source type of the term.
            source_id: The source id of the term.
        """
        if not definition and not link:
            return

        normalized_term = term.lower().strip()
        existing_term = self._existing_terms.get(normalized_term)
        if not existing_term:
            new_term = DictionaryTerm(
                term=normalized_term,
                definition=definition.strip() if definition else None,
                link=link.strip() if link else None,
                source_type=source_type,
                source_id=source_id,
            )
            await new_term.insert()
            self._existing_terms[normalized_term] = new_term
            self.created += 1
        elif (
            existing_term.definition != definition
            or existing_term.link != link
            or existing_term.source_type != source_type
            or existing_term.source_id != source_id
        ):
            existing_term.definition = definition.strip() if definition else None
            existing_term.link = link.strip() if link else None
            existing_term.source_type = source_type
            existing_term.source_id = source_id
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
        result = "\n\n**Gift Attributes:**"
        result += f"\n- Renown: `{gift_attributes.renown.value.title()}`"
        result += f"\n- Cost: `{gift_attributes.cost}`" if gift_attributes.cost else ""
        result += f"\n- Duration: `{gift_attributes.duration}`" if gift_attributes.duration else ""
        result += (
            f"\n- Minimum Renown: `{gift_attributes.minimum_renown}`"
            if gift_attributes.minimum_renown
            else ""
        )
        result += f"\n- Tribe: `{tribe_name}`" if tribe_name else ""
        result += f"\n- Auspice: `{auspice_name}`" if auspice_name else ""
        return result

    async def _sync_vampire_clan_terms(self) -> None:
        """Create dictionary terms for all vampire clans."""
        clans = await VampireClan.find().to_list()
        for clan in clans:
            definition = clan.description
            if clan.bane:
                definition += f"\n\n**Bane: {clan.bane.name.title()}**\n{clan.bane.description}"
            if clan.variant_bane:
                definition += f"\n\n**Variant Bane: {clan.variant_bane.name.title()}**\n{clan.variant_bane.description}"
            if clan.compulsion:
                definition += f"\n\n**Compulsion: {clan.compulsion.name.title()}**\n{clan.compulsion.description}"

            await self._upsert_term(
                clan.name,
                definition=definition,
                link=clan.link,
                source_type=DictionarySourceType.CLAN,
                source_id=clan.id,
            )

    async def _sync_werewolf_auspice_terms(self) -> None:
        """Create dictionary terms for all werewolf auspices."""
        for auspice in self._auspices:
            await self._upsert_term(
                auspice.name,
                definition=auspice.description,
                link=auspice.link,
                source_type=DictionarySourceType.AUSPICE,
                source_id=auspice.id,
            )

    async def _sync_werewolf_tribe_terms(self) -> None:
        """Create dictionary terms for all werewolf tribes."""
        for tribe in self._tribes:
            definition = tribe.description
            if tribe.renown:
                definition += f"\n\n- Renown: `{tribe.renown.value.title()}`"
            if tribe.patron_spirit:
                definition += f"\n- Patron Spirit: `{tribe.patron_spirit}`"
            if tribe.favor:
                definition += f"\n- Favor: `{tribe.favor}`"
            if tribe.ban:
                definition += f"\n- Ban: `{tribe.ban}`"
            await self._upsert_term(
                tribe.name,
                definition=tribe.description,
                link=tribe.link,
                source_type=DictionarySourceType.TRIBE,
                source_id=tribe.id,
            )

    async def _sync_subcategory_terms(self) -> None:
        """Create dictionary terms for trait subcategories with descriptions."""
        subcategories = await TraitSubcategory.find().to_list()

        for subcategory in subcategories:
            if not subcategory.description:
                continue

            definition = subcategory.description
            if subcategory.system:
                definition += f"\n\n**System:**\n{subcategory.system}"
            if subcategory.pool:
                definition += f"\n\n- Pool: `{subcategory.pool}`"

            await self._upsert_term(
                subcategory.name,
                definition=definition,
                source_type=DictionarySourceType.TRAIT_SUBCATEGORY,
                source_id=subcategory.id,
            )

    async def _sync_trait_terms(self) -> None:
        """Create dictionary terms for all non-archived traits."""
        traits = await Trait.find(Trait.is_archived == False).to_list()
        for trait in traits:
            if not trait.description:
                continue

            definition = trait.description
            if trait.gift_attributes:
                if trait.system:
                    definition += f"\n\n**System:**\n{trait.system}"

                definition += f"\n\n - {trait.sheet_section_name} > {trait.parent_category_name}"
                if trait.trait_subcategory_name:
                    definition += f" > {trait.trait_subcategory_name}"
                if trait.pool:
                    definition += f"\n- Pool: `{trait.pool}`"
                if trait.opposing_pool:
                    definition += f"\n- Opposing Pool: `{trait.opposing_pool}`"

                definition += self._build_gift_attributes_definition(
                    trait.gift_attributes,
                    tribe_name=self._tribes_by_id.get(trait.gift_attributes.tribe_id),
                    auspice_name=self._auspices_by_id.get(trait.gift_attributes.auspice_id),
                )
            if definition or trait.link:
                await self._upsert_term(
                    trait.name,
                    definition=definition,
                    link=trait.link,
                    source_type=DictionarySourceType.TRAIT,
                    source_id=trait.id,
                )

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
