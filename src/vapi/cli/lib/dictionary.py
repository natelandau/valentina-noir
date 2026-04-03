"""Dictionary term synchronization service."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vapi.cli.lib.sync_counts import SyncCounts
from vapi.constants import DictionarySourceType

if TYPE_CHECKING:
    from uuid import UUID
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_sheet import Trait, TraitSubcategory
from vapi.db.sql_models.dictionary import DictionaryTerm

logger = logging.getLogger("vapi")


class DictionaryService:
    """Build and sync global dictionary terms from PostgreSQL entities."""

    def __init__(self) -> None:
        self.counts = SyncCounts()
        self._tribes: list[WerewolfTribe] = []
        self._auspices: list[WerewolfAuspice] = []
        self._existing_terms: dict[str, DictionaryTerm] = {}

    async def sync_all(self) -> None:
        """Build dictionary terms for all entity types, then log counts."""
        self._tribes = list(await WerewolfTribe.all())
        self._auspices = list(await WerewolfAuspice.all())

        # Bulk-fetch all existing global terms to avoid N+1 queries in _upsert_term
        all_terms = await DictionaryTerm.filter(source_type__isnull=False)
        self._existing_terms = {t.term: t for t in all_terms}

        await self._sync_vampire_clan_terms()
        await self._sync_werewolf_auspice_terms()
        await self._sync_werewolf_tribe_terms()
        await self._sync_subcategory_terms()
        await self._sync_trait_terms()

        self.counts.total = await DictionaryTerm.all().count()
        self._log_counts()

    async def _upsert_term(
        self,
        term: str,
        *,
        definition: str | None = None,
        link: str | None = None,
        source_type: DictionarySourceType,
        source_id: UUID,
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
            await new_term.save()
            self._existing_terms[normalized_term] = new_term
            self.counts.created += 1
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
            self.counts.updated += 1

    async def _sync_vampire_clan_terms(self) -> None:
        """Create dictionary terms for all vampire clans."""
        clans = await VampireClan.all()
        for clan in clans:
            definition = clan.description or ""
            if clan.bane_name:
                definition += f"\n\n**Bane: {clan.bane_name.title()}**\n\n{clan.bane_description}"
            if clan.variant_bane_name:
                definition += f"\n\n**Variant Bane: {clan.variant_bane_name.title()}**\n\n{clan.variant_bane_description}"
            if clan.compulsion_name:
                definition += f"\n\n**Compulsion: {clan.compulsion_name.title()}**\n\n{clan.compulsion_description}"

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
            definition = tribe.description or ""
            if tribe.renown:
                definition += f"\n\n- **Renown:** {tribe.renown.value.title()}"
            if tribe.patron_spirit:
                definition += f"\n- **Patron Spirit:** {tribe.patron_spirit}"
            if tribe.favor:
                definition += f"\n- **Favor:** {tribe.favor}"
            if tribe.ban:
                definition += f"\n- **Ban:** {tribe.ban}"

            await self._upsert_term(
                tribe.name,
                definition=definition,
                link=tribe.link,
                source_type=DictionarySourceType.TRIBE,
                source_id=tribe.id,
            )

    async def _sync_subcategory_terms(self) -> None:
        """Create dictionary terms for trait subcategories with descriptions."""
        subcategories = await TraitSubcategory.all()
        for subcategory in subcategories:
            if not subcategory.description:
                continue

            definition = subcategory.description
            if subcategory.system:
                definition += f"\n\n**System:**\n{subcategory.system}"

            await self._upsert_term(
                subcategory.name,
                definition=definition,
                source_type=DictionarySourceType.TRAIT_SUBCATEGORY,
                source_id=subcategory.id,
            )

    async def _sync_trait_terms(self) -> None:
        """Create dictionary terms for all non-archived traits with descriptions."""
        traits = await Trait.filter(is_archived=False, description__isnull=False)
        for trait in traits:
            definition = trait.description
            if trait.system:
                definition += f"\n\n**System:**\n{trait.system}"

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
            "Bootstrapped PostgreSQL dictionary terms",
            extra={
                "num_created": self.counts.created,
                "num_updated": self.counts.updated,
                "num_total": self.counts.total,
                "component": "cli",
                "command": "bootstrap",
            },
        )
