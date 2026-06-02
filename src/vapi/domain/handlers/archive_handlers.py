"""Archive handlers.

Archive a top-level entity and cascade the archive to everything it owns. One
ArchiveContext (batch id + timestamp) is created per top-level action and
threaded through every nested handler, so the whole cascade shares a batch id
and can be restored as a unit. Every write is a guarded bulk update that flips
only currently-active rows (is_archived=False), making nested cascades
idempotent. Dice rolls are historical artifacts and are never cascade-archived.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from tortoise.models import Model
from uuid_utils import uuid7

from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.character import (
    Character,
    CharacterInventory,
    CharacterTrait,
    HunterAttributes,
    MageAttributes,
    Specialty,
    VampireAttributes,
    WerewolfAttributes,
)
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.company import Company, CompanySettings
from vapi.db.sql_models.diceroll import DiceRoll
from vapi.db.sql_models.dictionary import DictionaryTerm
from vapi.db.sql_models.notes import Note
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import CampaignExperience, User
from vapi.utils.time import time_now

logger = logging.getLogger("vapi")


@dataclass(frozen=True)
class ArchiveContext:
    """Shared identity for one top-level archive action.

    Args:
        batch_id: Stamped on every row the action archives; the restore key.
        now: Single timestamp stamped as archive_date across the whole action.
    """

    batch_id: UUID
    now: datetime


async def _archive_where(model: type[Model], ctx: ArchiveContext, **filters: object) -> int:
    """Archive every currently-active row of ``model`` matching ``filters``.

    Filtering on is_archived=False is what keeps the cascade idempotent and lets
    restore distinguish rows archived by this action from rows already archived.
    """
    return await model.filter(is_archived=False, **filters).update(
        is_archived=True,
        archive_date=ctx.now,
        archive_batch_id=ctx.batch_id,
    )


async def archive_s3_assets(fk_field: str, object_ids: list[UUID], ctx: ArchiveContext) -> int:
    """Archive all active S3 assets matching the given FK field and IDs."""
    return await _archive_where(S3Asset, ctx, **{f"{fk_field}__in": object_ids})


async def _archive_character_children(character_id: UUID, ctx: ArchiveContext) -> None:
    """Archive everything owned by a character (dice rolls excluded, D4)."""
    await archive_s3_assets("character_id", [character_id], ctx)
    await _archive_where(Trait, ctx, custom_for_character_id=character_id)
    await _archive_where(CharacterTrait, ctx, character_id=character_id)
    await _archive_where(CharacterInventory, ctx, character_id=character_id)
    await _archive_where(Specialty, ctx, character_id=character_id)
    for attr_model in (
        VampireAttributes,
        WerewolfAttributes,
        MageAttributes,
        HunterAttributes,
    ):
        await _archive_where(attr_model, ctx, character_id=character_id)
    await _archive_where(Note, ctx, character_id=character_id)


async def _archive_user_children(user_id: UUID, ctx: ArchiveContext) -> None:
    """Archive everything owned by a user (dice rolls excluded, D4).

    Cascades to PLAYER characters only (filtered by user_player_id); NPCs the
    user merely created are ownerless and survive.
    """
    await _archive_where(QuickRoll, ctx, user_id=user_id)
    await archive_s3_assets("user_parent_id", [user_id], ctx)
    await _archive_where(Note, ctx, user_id=user_id)
    await _archive_where(CampaignExperience, ctx, user_id=user_id)
    for character in await Character.filter(user_player_id=user_id, is_archived=False):
        await CharacterArchiveHandler(character=character, ctx=ctx).handle()


async def _archive_campaign_children(campaign_id: UUID, ctx: ArchiveContext) -> None:
    """Archive books, chapters, their notes/assets, characters (D1), and campaign data."""
    book_ids = [b.id for b in await CampaignBook.filter(campaign_id=campaign_id, is_archived=False)]
    chapter_ids = [
        c.id for c in await CampaignChapter.filter(book_id__in=book_ids, is_archived=False)
    ]

    await _archive_where(CampaignChapter, ctx, book_id__in=book_ids)
    await _archive_where(CampaignBook, ctx, campaign_id=campaign_id)

    await archive_s3_assets("chapter_id", chapter_ids, ctx)
    await archive_s3_assets("book_id", book_ids, ctx)
    await archive_s3_assets("campaign_id", [campaign_id], ctx)

    await _archive_where(Note, ctx, chapter_id__in=chapter_ids)
    await _archive_where(Note, ctx, book_id__in=book_ids)
    await _archive_where(Note, ctx, campaign_id=campaign_id)
    await _archive_where(CampaignExperience, ctx, campaign_id=campaign_id)

    for character in await Character.filter(campaign_id=campaign_id, is_archived=False):
        await CharacterArchiveHandler(character=character, ctx=ctx).handle()


class CharacterArchiveHandler:
    """Archive a character and everything it owns."""

    def __init__(self, character: Character, ctx: ArchiveContext) -> None:
        """Initialize with the character and the shared archive context."""
        self.character = character
        self.ctx = ctx

    async def handle(self) -> None:
        """Flip the character (idempotent) and cascade to its children."""
        await _archive_where(Character, self.ctx, id=self.character.id)
        await _archive_character_children(self.character.id, self.ctx)


class CampaignArchiveHandler:
    """Archive a campaign and everything under it."""

    def __init__(self, campaign: Campaign, ctx: ArchiveContext) -> None:
        """Initialize with the campaign and the shared archive context."""
        self.campaign = campaign
        self.ctx = ctx

    async def handle(self) -> None:
        """Flip the campaign (idempotent) and cascade to its children."""
        await _archive_where(Campaign, self.ctx, id=self.campaign.id)
        await _archive_campaign_children(self.campaign.id, self.ctx)


class UserArchiveHandler:
    """Archive a user and everything they own."""

    def __init__(self, user: User, ctx: ArchiveContext) -> None:
        """Initialize with the user and the shared archive context."""
        self.user = user
        self.ctx = ctx

    async def handle(self) -> None:
        """Flip the user (idempotent) and cascade to their owned data."""
        await _archive_where(User, self.ctx, id=self.user.id)
        await _archive_user_children(self.user.id, self.ctx)


class CompanyArchiveHandler:
    """Archive a company and every entity belonging to it."""

    def __init__(self, company: Company, ctx: ArchiveContext) -> None:
        """Initialize with the company and the shared archive context."""
        self.company = company
        self.ctx = ctx

    async def _archive_company_scoped(self) -> None:
        """Archive models scoped directly by company_id (incl. dice rolls)."""
        for model in (Note, DictionaryTerm, CharacterConcept, DiceRoll, S3Asset, CompanySettings):
            await _archive_where(model, self.ctx, company_id=self.company.id)

    async def handle(self) -> None:
        """Cascade through all child entities, then flip the company itself."""
        for campaign in await Campaign.filter(company_id=self.company.id, is_archived=False):
            await CampaignArchiveHandler(campaign=campaign, ctx=self.ctx).handle()

        for character in await Character.filter(company_id=self.company.id, is_archived=False):
            await CharacterArchiveHandler(character=character, ctx=self.ctx).handle()

        for user in await User.filter(company_id=self.company.id, is_archived=False):
            await UserArchiveHandler(user=user, ctx=self.ctx).handle()

        await self._archive_company_scoped()
        await _archive_where(Company, self.ctx, id=self.company.id)


def _new_context() -> ArchiveContext:
    """Mint a fresh archive context for a top-level action."""
    return ArchiveContext(batch_id=UUID(str(uuid7())), now=time_now())


async def archive_character(character: Character) -> ArchiveContext:
    """Archive a character and its subtree as one batch; returns the context."""
    ctx = _new_context()
    await CharacterArchiveHandler(character=character, ctx=ctx).handle()
    return ctx


async def archive_campaign(campaign: Campaign) -> ArchiveContext:
    """Archive a campaign and its subtree as one batch; returns the context."""
    ctx = _new_context()
    await CampaignArchiveHandler(campaign=campaign, ctx=ctx).handle()
    return ctx


async def archive_user(user: User) -> ArchiveContext:
    """Archive a user and their owned data as one batch; returns the context."""
    ctx = _new_context()
    await UserArchiveHandler(user=user, ctx=ctx).handle()
    return ctx


async def archive_company(company: Company) -> ArchiveContext:
    """Archive a company and its entire tenant as one batch; returns the context."""
    ctx = _new_context()
    await CompanyArchiveHandler(company=company, ctx=ctx).handle()
    return ctx


async def cascade_archive_user(user: User) -> ArchiveContext:
    """Cascade-archive a user's owned data under the user row's existing batch.

    The caller has already archived the user record (e.g. via ``user.save()``),
    so this reuses that row's batch id and timestamp, keeping the user and their
    owned data in one restorable batch. Dice rolls are intentionally not touched.
    """
    ctx = ArchiveContext(batch_id=user.archive_batch_id, now=user.archive_date)
    await _archive_user_children(user.id, ctx)
    return ctx
