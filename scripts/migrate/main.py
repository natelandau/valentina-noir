"""Migration script entry point.

Migrate data from the old Valentina Discord bot database to the new Valentina Noir API database.

Usage:
    uv run python -m scripts.migrate.main --dry-run
    uv run python -m scripts.migrate.main
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID as StdUUID  # noqa: N811

from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.campaign import Campaign
from vapi.db.sql_models.character import (
    CharacterInventory,
    CharacterTrait,
    HunterAttributes,
    MageAttributes,
    Specialty,
    VampireAttributes,
    WerewolfAttributes,
)
from vapi.db.sql_models.character_sheet import (
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)
from vapi.db.sql_models.company import Company, CompanySettings
from vapi.db.sql_models.diceroll import DiceRoll, DiceRollResult
from vapi.db.sql_models.notes import Note
from vapi.db.sql_models.user import CampaignExperience, User
from vapi.domain.services.aws_service import AWSS3Service

from .id_map import IDMap
from .new_db import close_new_db, connect_new_db
from .old_db import (
    connect_old_db,
    read_campaign_books,
    read_campaign_chapters,
    read_campaigns,
    read_character_traits,
    read_characters,
    read_guilds,
    read_inventory_items,
    read_notes,
    read_roll_statistics,
    read_users,
)
from .s3_copy import S3Migrator
from .transformers import (
    build_campaign_experience_list,
    transform_campaign,
    transform_campaign_book,
    transform_campaign_chapter,
    transform_character,
    transform_guild_to_company,
    transform_inventory_item,
    transform_note,
    transform_roll_statistic,
    transform_user,
)

if TYPE_CHECKING:
    from uuid import UUID

    from pymongo.asynchronous.database import AsyncDatabase
    from tortoise.models import Model as TortoiseModel

logger = logging.getLogger("migrate")
# Minimum trait name length before padding with underscores
MIN_TRAIT_NAME_LENGTH = 3


def _std_id(obj: Any) -> StdUUID:
    """Convert a model's id (uuid_utils.UUID) to stdlib uuid.UUID.

    Tortoise's UUIDField.to_python_value rejects uuid_utils.UUID when passed
    as a FK value during model construction. This converts to stdlib UUID.
    """
    return StdUUID(str(obj.id))


# Old trait name (lowercase) → corrected name for matching against new blueprints
_TRAIT_NAME_REMAPS: dict[str, str] = {
    "bloodpool": "Blood Pool",
    "computer": "Technology",
    "crafts": "Craft",
    "lockpicking": "Larceny",
    "technomancy": "The Path of Technomancy",
    "thaumaturgy: weather control": "Weather Control",
    "lure of flames": "The Lure Of Flames",
}


class MigrationStats:
    """Track migration statistics for summary output."""

    def __init__(self) -> None:
        self.created: dict[str, int] = {}
        self.skipped: dict[str, int] = {}
        self.failed: dict[str, int] = {}
        self.failures: list[str] = []

    def record_created(self, entity_type: str) -> None:
        """Record a successfully created entity.

        Args:
            entity_type: The entity type label.
        """
        self.created[entity_type] = self.created.get(entity_type, 0) + 1

    def record_skipped(self, entity_type: str, reason: str) -> None:
        """Record a skipped entity.

        Args:
            entity_type: The entity type label.
            reason: Human-readable reason for skipping.
        """
        self.skipped[entity_type] = self.skipped.get(entity_type, 0) + 1
        logger.info("SKIPPED %s: %s", entity_type, reason)

    def record_failed(self, entity_type: str, old_id: Any, error: Exception) -> None:
        """Record a failed entity.

        Args:
            entity_type: The entity type label.
            old_id: The old entity ID for reference.
            error: The exception that caused the failure.
        """
        self.failed[entity_type] = self.failed.get(entity_type, 0) + 1
        msg = f"FAILED {entity_type} (old_id={old_id}): {error}"
        self.failures.append(msg)
        logger.error(msg)

    def print_summary(self, *, dry_run: bool = False) -> None:
        """Print migration summary to stdout.

        Args:
            dry_run: If True, prefix output lines with [DRY RUN].
        """
        prefix = "[DRY RUN] " if dry_run else ""
        print(f"\n{prefix}Migration Summary")  # noqa: T201
        print("=" * 40)  # noqa: T201
        for entity_type, count in sorted(self.created.items()):
            print(f"  {prefix}Created {entity_type}: {count}")  # noqa: T201
        for entity_type, count in sorted(self.skipped.items()):
            print(f"  {prefix}Skipped {entity_type}: {count}")  # noqa: T201
        for entity_type, count in sorted(self.failed.items()):
            print(f"  {prefix}Failed {entity_type}: {count}")  # noqa: T201
        if self.failures:
            print(f"\n{prefix}Failure Details:")  # noqa: T201
            for failure in self.failures:
                print(f"  {failure}")  # noqa: T201


async def _save(obj: TortoiseModel, *, dry_run: bool) -> None:
    """Save a Tortoise model instance, respecting dry-run mode.

    UUID v7 default means the ID is populated at construction time,
    so it is available for ID map lookups even in dry-run mode.

    Args:
        obj: The Tortoise model instance to save.
        dry_run: If True, skip the actual save.
    """
    if not dry_run:
        await obj.save()


async def _clean_migrated_data(*, dry_run: bool) -> None:
    """Truncate all non-constant tables in reverse-dependency order for idempotency.

    Constants (CharSheetSection, TraitCategory, Trait, VampireClan, etc.) are
    seeded by ``duty seed`` and left untouched.

    Args:
        dry_run: If True, skip truncation.
    """
    if dry_run:
        return

    models_to_clean: list[type[TortoiseModel]] = [
        DiceRollResult,
        DiceRoll,
        Note,
        S3Asset,
        CharacterTrait,
        CharacterInventory,
        Specialty,
        VampireAttributes,
        WerewolfAttributes,
        MageAttributes,
        HunterAttributes,
        CampaignExperience,
        Campaign,
        User,
        CompanySettings,
        Company,
    ]
    for model in models_to_clean:
        await model.all().delete()
    logger.info("Cleaned all non-constant tables")


def _has_activity(user: dict[str, Any], characters: list[dict[str, Any]]) -> bool:
    """Check if a user has characters or campaign experience.

    Use this to filter out users who never participated in a guild.

    Args:
        user: The old user document.
        characters: All characters in the guild.

    Returns:
        True if the user should be migrated.
    """
    user_id = user["_id"]
    if user.get("campaign_experience"):
        return True
    return any(
        c.get("user_creator") == user_id or c.get("user_owner") == user_id for c in characters
    )


async def _migrate_users(
    guild: dict[str, Any],
    old_users: list[dict[str, Any]],
    all_characters: list[dict[str, Any]],
    company: Any,
    id_map: IDMap,
    stats: MigrationStats,
    *,
    dry_run: bool,
) -> None:
    """Migrate users belonging to a guild, filtered to active participants only.

    Args:
        guild: The old Guild document.
        old_users: All user documents from the old database.
        all_characters: All character documents for this guild.
        company: The newly created Company document.
        id_map: The ID map registry.
        stats: Migration statistics tracker.
        dry_run: If True, don't write to the new database.
    """
    guild_id = guild["_id"]

    for user in old_users:
        if not _has_activity(user, all_characters):
            stats.record_skipped("user", f"no activity: {user['_id']}")
            continue
        # Only migrate users who belong to this guild
        if guild_id not in user.get("guilds", []):
            continue
        try:
            new_user = transform_user(user, guild, _std_id(company))
            await _save(new_user, dry_run=dry_run)
            id_map.add("user", (user["_id"], guild_id), _std_id(new_user))
            stats.record_created("user")
            logger.info("User %s → %s", user["_id"], new_user.id)
        except Exception as e:  # noqa: BLE001
            stats.record_failed("user", user["_id"], e)


async def _migrate_campaigns(
    old_db: AsyncDatabase,
    guild_id: int,
    company: Any,
    id_map: IDMap,
    stats: MigrationStats,
    *,
    dry_run: bool,
) -> None:
    """Migrate campaigns, books, and chapters for a guild.

    Args:
        old_db: The old database connection.
        guild_id: The old guild ID.
        company: The newly created Company document.
        id_map: The ID map registry.
        stats: Migration statistics tracker.
        dry_run: If True, don't write to the new database.
    """
    old_campaigns = await read_campaigns(old_db, guild_id)
    for campaign in old_campaigns:
        try:
            new_campaign = transform_campaign(campaign, _std_id(company))
            await _save(new_campaign, dry_run=dry_run)
            old_campaign_id = str(campaign["_id"])
            id_map.add("campaign", old_campaign_id, _std_id(new_campaign))
            stats.record_created("campaign")
            logger.info("Campaign %s → %s", old_campaign_id, new_campaign.id)

            await _migrate_books(
                old_db, old_campaign_id, new_campaign, id_map, stats, dry_run=dry_run
            )
        except Exception as e:  # noqa: BLE001
            stats.record_failed("campaign", campaign.get("_id"), e)


async def _migrate_books(
    old_db: AsyncDatabase,
    old_campaign_id: str,
    new_campaign: Any,
    id_map: IDMap,
    stats: MigrationStats,
    *,
    dry_run: bool,
) -> None:
    """Migrate books and chapters for a campaign.

    Args:
        old_db: The old database connection.
        old_campaign_id: The old campaign ID string.
        new_campaign: The newly created Campaign document.
        id_map: The ID map registry.
        stats: Migration statistics tracker.
        dry_run: If True, don't write to the new database.
    """
    old_books = await read_campaign_books(old_db, old_campaign_id)
    for book in old_books:
        try:
            new_book = transform_campaign_book(book, _std_id(new_campaign))
            await _save(new_book, dry_run=dry_run)
            old_book_id = str(book["_id"])
            id_map.add("book", old_book_id, _std_id(new_book))
            stats.record_created("book")

            old_chapters = await read_campaign_chapters(old_db, old_book_id)
            for chapter in old_chapters:
                try:
                    new_chapter = transform_campaign_chapter(chapter, _std_id(new_book))
                    await _save(new_chapter, dry_run=dry_run)
                    id_map.add("chapter", str(chapter["_id"]), _std_id(new_chapter))
                    stats.record_created("chapter")
                except Exception as e:  # noqa: BLE001
                    stats.record_failed("chapter", chapter.get("_id"), e)
        except Exception as e:  # noqa: BLE001
            stats.record_failed("book", book.get("_id"), e)


async def _backfill_campaign_experience(
    old_users: list[dict[str, Any]],
    guild_id: int,
    id_map: IDMap,
    stats: MigrationStats,
    *,
    dry_run: bool,
) -> None:
    """Backfill campaign experience onto already-migrated users.

    Creates CampaignExperience rows and updates lifetime totals on the User.

    Args:
        old_users: All user documents from the old database.
        guild_id: The old guild ID for user lookup key.
        id_map: The ID map registry.
        stats: Migration statistics tracker.
        dry_run: If True, don't write to the new database.
    """
    for user in old_users:
        user_key = (user["_id"], guild_id)
        new_user_id = id_map.get("user", user_key)
        if new_user_id is None:
            continue
        old_experience = user.get("campaign_experience", {})
        if not old_experience:
            continue
        try:
            experiences = build_campaign_experience_list(old_experience, id_map)
            total_xp = sum(e.xp_total for e in experiences)
            total_cp = sum(e.cool_points for e in experiences)

            for exp in experiences:
                exp.user_id = new_user_id
                await _save(exp, dry_run=dry_run)
                stats.record_created("campaign_experience")

            if experiences and not dry_run:
                await User.filter(id=new_user_id).update(
                    lifetime_xp=total_xp, lifetime_cool_points=total_cp
                )
        except Exception as e:  # noqa: BLE001
            stats.record_failed("campaign_experience", user["_id"], e)


async def _migrate_character_contents(
    old_db: AsyncDatabase,
    char: dict[str, Any],
    new_char: Any,
    company: Any,
    s3: S3Migrator,
    aws_service: AWSS3Service,
    stats: MigrationStats,
    *,
    dry_run: bool,
) -> None:
    """Migrate traits, inventory, and images for a single character.

    Args:
        old_db: The old database connection.
        char: The old character document.
        new_char: The newly created Character document.
        company: The newly created Company document.
        s3: The S3 migrator.
        aws_service: The AWS S3 service for uploading assets.
        stats: Migration statistics tracker.
        dry_run: If True, don't write to the new database or upload S3 objects.
    """
    old_char_id = str(char["_id"])

    # Traits
    old_traits = await read_character_traits(old_db, old_char_id)
    for trait_doc in old_traits:
        try:
            await _migrate_trait(trait_doc, _std_id(new_char), stats, dry_run=dry_run)
        except Exception as e:  # noqa: BLE001
            stats.record_failed("trait", trait_doc.get("_id"), e)

    # Inventory
    old_items = await read_inventory_items(old_db, old_char_id)
    for item in old_items:
        try:
            new_item = transform_inventory_item(item, _std_id(new_char))
            await _save(new_item, dry_run=dry_run)
            stats.record_created("inventory")
        except Exception as e:  # noqa: BLE001
            stats.record_failed("inventory", item.get("_id"), e)

    # Images → S3Asset via AWSS3Service
    for old_key in char.get("images", []):
        try:
            if dry_run:
                logger.info(
                    "[DRY RUN] Would upload %s for character %s", Path(old_key).name, new_char.id
                )
                stats.record_created("s3_asset")
            else:
                data = s3.download_object(old_key)
                filename = Path(old_key).name
                mime_type = mimetypes.guess_type(old_key)[0] or "application/octet-stream"
                await aws_service.upload_asset(
                    company_id=_std_id(company),
                    uploaded_by_id=new_char.user_creator_id,
                    parent_id=_std_id(new_char),
                    parent_fk_field="character_id",
                    data=data,
                    filename=filename,
                    mime_type=mime_type,
                )
                stats.record_created("s3_asset")
        except Exception as e:  # noqa: BLE001
            stats.record_failed("s3_asset", old_key, e)


async def _migrate_characters(
    old_db: AsyncDatabase,
    all_characters: list[dict[str, Any]],
    guild_id: int,
    company: Any,
    id_map: IDMap,
    s3: S3Migrator,
    aws_service: AWSS3Service,
    stats: MigrationStats,
    *,
    dry_run: bool,
) -> None:
    """Migrate characters, traits, inventory, and images for a guild.

    Args:
        old_db: The old database connection.
        all_characters: All character documents for this guild.
        guild_id: The old guild ID.
        company: The newly created Company document.
        id_map: The ID map registry.
        s3: The S3 migrator.
        aws_service: The AWS S3 service for uploading assets.
        stats: Migration statistics tracker.
        dry_run: If True, don't write to the new database or upload S3 objects.
    """
    # Created on first use to avoid empty campaigns when all chars have campaigns
    uncategorized_campaign_id: UUID | None = None

    for char in all_characters:
        old_char_id = str(char["_id"])

        # Determine campaign_id - fall back to an uncategorized campaign if needed
        old_campaign_ref = char.get("campaign")
        if old_campaign_ref:
            campaign_id = id_map.get("campaign", str(old_campaign_ref))
            if campaign_id is None:
                stats.record_skipped("character", f"campaign not migrated: {old_char_id}")
                continue
        else:
            # Create the uncategorized placeholder campaign once per company
            if uncategorized_campaign_id is None:
                uncat = Campaign(name="Uncategorized", company_id=_std_id(company))
                await _save(uncat, dry_run=dry_run)
                uncategorized_campaign_id = _std_id(uncat)
                stats.record_created("campaign")
            campaign_id = uncategorized_campaign_id

        try:
            new_char, char_attrs = await transform_character(
                char, id_map, _std_id(company), campaign_id, guild_id
            )
            await _save(new_char, dry_run=dry_run)
            for attr in char_attrs:
                attr.character_id = _std_id(new_char)
                await _save(attr, dry_run=dry_run)
            id_map.add("character", old_char_id, _std_id(new_char))
            stats.record_created("character")
            logger.info("Character %s → %s", old_char_id, new_char.id)

            await _migrate_character_contents(
                old_db, char, new_char, company, s3, aws_service, stats, dry_run=dry_run
            )
        except Exception as e:  # noqa: BLE001
            stats.record_failed("character", old_char_id, e)


async def _migrate_notes(
    old_db: AsyncDatabase,
    guild_id: int,
    id_map: IDMap,
    stats: MigrationStats,
    *,
    dry_run: bool,
) -> None:
    """Migrate notes for a guild.

    Args:
        old_db: The old database connection.
        guild_id: The old guild ID.
        id_map: The ID map registry.
        stats: Migration statistics tracker.
        dry_run: If True, don't write to the new database.
    """
    old_notes = await read_notes(old_db, guild_id=guild_id)
    for note in old_notes:
        try:
            new_note = transform_note(note, id_map, guild_id)
            if new_note is None:
                stats.record_skipped("note", f"transform returned None: {note.get('_id')}")
                continue
            await _save(new_note, dry_run=dry_run)
            stats.record_created("note")
        except Exception as e:  # noqa: BLE001
            stats.record_failed("note", note.get("_id"), e)


async def _migrate_dice_rolls(
    old_db: AsyncDatabase,
    guild_id: int,
    id_map: IDMap,
    stats: MigrationStats,
    *,
    dry_run: bool,
) -> None:
    """Migrate roll statistics as DiceRoll + DiceRollResult documents for a guild.

    Args:
        old_db: The old database connection.
        guild_id: The old guild ID.
        id_map: The ID map registry.
        stats: Migration statistics tracker.
        dry_run: If True, don't write to the new database.
    """
    old_rolls = await read_roll_statistics(old_db, guild_id)
    for stat_doc in old_rolls:
        try:
            result = transform_roll_statistic(stat_doc, id_map, guild_id)
            if result is None:
                stats.record_skipped("diceroll", f"no company: {stat_doc.get('_id')}")
                continue

            dice_roll, roll_result = result
            await _save(dice_roll, dry_run=dry_run)
            roll_result.dice_roll_id = _std_id(dice_roll)
            await _save(roll_result, dry_run=dry_run)

            # Best-effort M2M trait linking from old trait names
            old_trait_names = stat_doc.get("traits", [])
            for tname in old_trait_names:
                matched = await Trait.filter(name=tname.title(), is_custom=False).first()
                if matched and not dry_run:
                    await dice_roll.traits.add(matched)

            stats.record_created("diceroll")
        except Exception as e:  # noqa: BLE001
            stats.record_failed("diceroll", stat_doc.get("_id"), e)


async def migrate_guild(
    guild: dict[str, Any],
    old_db: AsyncDatabase,
    id_map: IDMap,
    s3: S3Migrator,
    aws_service: AWSS3Service,
    stats: MigrationStats,
    *,
    dry_run: bool,
) -> None:
    """Migrate a single guild and all its dependent data.

    Processes the full dependency chain: company → users → campaigns/books/chapters →
    characters/traits/inventory → notes → dice rolls.

    Args:
        guild: The old Guild document.
        old_db: The old database connection.
        id_map: The ID map registry.
        s3: The S3 migrator.
        aws_service: The AWS S3 service for uploading assets.
        stats: Migration statistics tracker.
        dry_run: If True, don't write to new DB or upload S3 objects.
    """
    guild_id = guild["_id"]
    logger.info("Migrating guild: %s (id=%s)", guild.get("name"), guild_id)

    # Step 1: Guild → Company + CompanySettings
    try:
        company, company_settings = transform_guild_to_company(guild)
        await _save(company, dry_run=dry_run)
        company_settings.company_id = _std_id(company)
        await _save(company_settings, dry_run=dry_run)
        id_map.add("guild", guild_id, _std_id(company))
        stats.record_created("company")
        logger.info("Guild %s → Company %s", guild_id, company.id)
        s3.record_company(company.id)
    except Exception as e:  # noqa: BLE001
        stats.record_failed("company", guild_id, e)
        return

    # Step 2: Users
    all_characters = await read_characters(old_db, guild_id)
    old_users = await read_users(old_db)
    await _migrate_users(guild, old_users, all_characters, company, id_map, stats, dry_run=dry_run)

    # Step 3: Campaigns + Books + Chapters
    await _migrate_campaigns(old_db, guild_id, company, id_map, stats, dry_run=dry_run)

    # Step 4: Backfill User Campaign Experience
    await _backfill_campaign_experience(old_users, guild_id, id_map, stats, dry_run=dry_run)

    # Step 5: Characters + Traits + Inventory + Images
    await _migrate_characters(
        old_db, all_characters, guild_id, company, id_map, s3, aws_service, stats, dry_run=dry_run
    )

    # Step 6: Notes
    await _migrate_notes(old_db, guild_id, id_map, stats, dry_run=dry_run)

    # Step 7: RollStatistic → DiceRoll + DiceRollResult
    await _migrate_dice_rolls(old_db, guild_id, id_map, stats, dry_run=dry_run)


async def _migrate_trait(  # noqa: C901, PLR0915
    trait_doc: dict[str, Any],
    character_id: UUID,
    stats: MigrationStats,
    *,
    dry_run: bool,
) -> None:
    """Migrate a single character trait, matching against an existing blueprint or creating a custom one.

    Args:
        trait_doc: The old CharacterTrait document.
        character_id: The new Character ID.
        stats: Migration statistics.
        dry_run: If True, skip saves.
    """
    advantages_section = await CharSheetSection.filter(name="Advantages").first()
    abilities_section = await CharSheetSection.filter(name="Abilities").first()
    other_section = await CharSheetSection.filter(name="Other").first()
    subcategory = await TraitSubcategory.filter(name=trait_doc.get("name", "")).first()
    trait_name = trait_doc.get("name", "")
    trait_value = trait_doc.get("value", 0)

    # Remap known trait names before matching
    trait_name = _TRAIT_NAME_REMAPS.get(trait_name.lower(), trait_name)
    if trait_name == "Desperation":
        return

    # Try to find an existing trait blueprint by name (case-insensitive via title())
    existing_trait = await Trait.filter(
        name=trait_name.title(),
        is_custom=False,
    ).first()

    if existing_trait and trait_name != "Surveillance":
        char_trait = CharacterTrait(
            character_id=character_id,
            trait_id=StdUUID(str(existing_trait.id)),
            value=trait_value,
        )

        if (
            existing_trait.sheet_section_id in [advantages_section.id, other_section.id]
            and char_trait.value == 0
        ):
            return

        await _save(char_trait, dry_run=dry_run)
        stats.record_created("trait_matched")
    elif subcategory:
        subcategory_traits = await Trait.filter(subcategory_id=subcategory.id)
        for dot in range(trait_value):
            trait_to_assign = subcategory_traits[dot] if dot < len(subcategory_traits) else None
            if trait_to_assign:
                char_trait = CharacterTrait(
                    character_id=character_id,
                    trait_id=StdUUID(str(trait_to_assign.id)),
                    value=1,
                )
                await _save(char_trait, dry_run=dry_run)
                stats.record_created("trait_matched")
    elif trait_name == "Surveillance":
        category = await TraitCategory.filter(
            name="Social",
            sheet_section_id=abilities_section.id,
        ).first()
        custom_trait = Trait(
            name=(
                trait_name.title()
                if len(trait_name) >= MIN_TRAIT_NAME_LENGTH
                else f"{trait_name}___"
            ),
            is_custom=True,
            custom_for_character_id=character_id,
            sheet_section_id=StdUUID(str(abilities_section.id)),
            category_id=StdUUID(str(category.id)),
            max_value=trait_doc.get("max_value", 5),
        )
        await _save(custom_trait, dry_run=dry_run)
        char_trait = CharacterTrait(
            character_id=character_id,
            trait_id=StdUUID(str(custom_trait.id)),
            value=trait_value,
        )
        await _save(char_trait, dry_run=dry_run)
        stats.record_created("trait_custom")
    else:
        old_category_name = trait_doc.get("category_name")
        section = None
        category = None

        if old_category_name == "TALENTS":
            section = abilities_section
            category = await TraitCategory.filter(
                name="Physical",
                sheet_section_id=abilities_section.id,
            ).first()

        elif old_category_name == "SKILLS":
            section = abilities_section
            category = await TraitCategory.filter(
                name="Social",
                sheet_section_id=abilities_section.id,
            ).first()
        elif old_category_name == "KNOWLEDGES":
            section = abilities_section
            category = await TraitCategory.filter(
                name="Mental",
                sheet_section_id=abilities_section.id,
            ).first()
        else:
            possible_categories = await TraitCategory.filter(name=old_category_name.title())
            if len(possible_categories) == 1:
                category = possible_categories[0]
                section = await CharSheetSection.filter(id=category.sheet_section_id).first()

        if section and category:
            custom_trait = Trait(
                name=(
                    trait_name.title()
                    if len(trait_name) >= MIN_TRAIT_NAME_LENGTH
                    else f"{trait_name}___"
                ),
                is_custom=True,
                custom_for_character_id=character_id,
                sheet_section_id=StdUUID(str(section.id)),
                category_id=StdUUID(str(category.id)),
                max_value=trait_doc.get("max_value", 5),
            )
            await _save(custom_trait, dry_run=dry_run)

            char_trait = CharacterTrait(
                character_id=character_id,
                trait_id=StdUUID(str(custom_trait.id)),
                value=trait_value,
            )
            await _save(char_trait, dry_run=dry_run)
            stats.record_created("trait_custom")
        else:
            stats.record_failed(
                "trait",
                trait_doc.get("_id"),
                ValueError("No sheet section or category found"),
            )


async def run_migration(*, dry_run: bool) -> None:
    """Run the full migration pipeline.

    Args:
        dry_run: If True, log all operations without writing.
    """
    prefix = "[DRY RUN] " if dry_run else ""
    logger.info("%sStarting migration", prefix)

    # Connect to databases
    await connect_new_db()
    old_client, old_db = await connect_old_db()

    id_map = IDMap()
    stats = MigrationStats()
    s3 = S3Migrator(dry_run=dry_run)
    aws_service = AWSS3Service()

    # Clean up S3 objects and DB records from any previous migration run
    await s3.cleanup_previous_run()
    await _clean_migrated_data(dry_run=dry_run)

    try:
        guilds = await read_guilds(old_db)
        logger.info("%sFound %d guilds to migrate", prefix, len(guilds))

        for guild in guilds:
            await migrate_guild(guild, old_db, id_map, s3, aws_service, stats, dry_run=dry_run)

        # Save company ID log for future cleanup
        s3.save_log()

    finally:
        await old_client.close()
        await close_new_db()

    stats.print_summary(dry_run=dry_run)


def main() -> None:
    """Parse arguments and run the migration."""
    parser = argparse.ArgumentParser(description="Migrate old Valentina DB to Valentina Noir")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log all operations without writing to the new database or uploading S3 objects",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    asyncio.run(run_migration(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
