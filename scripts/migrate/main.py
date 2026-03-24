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
from pathlib import Path
from typing import TYPE_CHECKING, Any

from beanie import PydanticObjectId

from vapi.config import settings
from vapi.db.models.campaign import Campaign
from vapi.db.models.character import CharacterTrait
from vapi.db.models.constants.trait import Trait

from .id_map import IDMap
from .new_db import connect_new_db
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
    from pymongo.asynchronous.database import AsyncDatabase

logger = logging.getLogger("migrate")

# Minimum trait name length before padding with underscores
MIN_TRAIT_NAME_LENGTH = 3

# Collected during migration for review
_unmatched_traits: list[str] = []

# Old trait name (lowercase) → corrected name for matching against new blueprints
_TRAIT_NAME_REMAPS: dict[str, str] = {
    "bloodpool": "Blood Pool",
    "computer": "Technology",
    "crafts": "Craft",
    "lockpicking": "Larceny",
    "technomancy": "The Path of Technomancy",
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


async def _save(doc: Any, *, dry_run: bool) -> None:
    """Save a document, respecting dry-run mode.

    In dry-run mode, assigns a synthetic ObjectId so downstream ID map
    lookups still work correctly.

    Args:
        doc: The Beanie document to save.
        dry_run: If True, skip the actual save.
    """
    if dry_run:
        if doc.id is None:
            from bson import ObjectId

            doc.id = PydanticObjectId(ObjectId())
    else:
        await doc.insert()


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
) -> list[PydanticObjectId]:
    """Migrate users belonging to a guild, filtered to active participants only.

    Args:
        guild: The old Guild document.
        old_users: All user documents from the old database.
        all_characters: All character documents for this guild.
        company: The newly created Company document.
        id_map: The ID map registry.
        stats: Migration statistics tracker.
        dry_run: If True, don't write to the new database.

    Returns:
        List of new user IDs created in this company.
    """
    guild_id = guild["_id"]
    user_ids_in_company: list[PydanticObjectId] = []

    for user in old_users:
        if not _has_activity(user, all_characters):
            stats.record_skipped("user", f"no activity: {user['_id']}")
            continue
        # Only migrate users who belong to this guild
        if guild_id not in user.get("guilds", []):
            continue
        try:
            new_user = transform_user(user, guild, company.id)
            await _save(new_user, dry_run=dry_run)
            id_map.add("user", (user["_id"], guild_id), new_user.id)
            user_ids_in_company.append(new_user.id)
            stats.record_created("user")
            logger.info("User %s → %s", user["_id"], new_user.id)
        except Exception as e:  # noqa: BLE001
            stats.record_failed("user", user["_id"], e)

    return user_ids_in_company


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
            new_campaign = transform_campaign(campaign, company.id)
            await _save(new_campaign, dry_run=dry_run)
            old_campaign_id = str(campaign["_id"])
            id_map.add("campaign", old_campaign_id, new_campaign.id)
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
            new_book = transform_campaign_book(book, new_campaign.id)
            await _save(new_book, dry_run=dry_run)
            old_book_id = str(book["_id"])
            id_map.add("book", old_book_id, new_book.id)
            stats.record_created("book")

            old_chapters = await read_campaign_chapters(old_db, old_book_id)
            for chapter in old_chapters:
                try:
                    new_chapter = transform_campaign_chapter(chapter, new_book.id)
                    await _save(new_chapter, dry_run=dry_run)
                    id_map.add("chapter", str(chapter["_id"]), new_chapter.id)
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
            if experiences and not dry_run:
                from vapi.db.models.user import User as UserModel

                db_user = await UserModel.get(new_user_id)
                if db_user:
                    db_user.campaign_experience = experiences
                    # Sum totals for lifetime fields
                    db_user.lifetime_xp = sum(e.xp_total for e in experiences)
                    db_user.lifetime_cool_points = sum(e.cool_points for e in experiences)
                    await db_user.save()
            elif experiences:
                stats.record_created("campaign_experience")
        except Exception as e:  # noqa: BLE001
            stats.record_failed("campaign_experience", user["_id"], e)


async def _migrate_character_contents(
    old_db: AsyncDatabase,
    char: dict[str, Any],
    new_char: Any,
    company: Any,
    s3: S3Migrator,
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
        stats: Migration statistics tracker.
        dry_run: If True, don't write to the new database or copy S3 objects.
    """
    old_char_id = str(char["_id"])

    # Traits
    old_traits = await read_character_traits(old_db, old_char_id)
    for trait_doc in old_traits:
        try:
            await _migrate_trait(trait_doc, new_char.id, stats, dry_run=dry_run)
        except Exception as e:  # noqa: BLE001
            stats.record_failed("trait", trait_doc.get("_id"), e)

    # Inventory
    old_items = await read_inventory_items(old_db, old_char_id)
    for item in old_items:
        try:
            new_item = transform_inventory_item(item, new_char.id)
            await _save(new_item, dry_run=dry_run)
            stats.record_created("inventory")
        except Exception as e:  # noqa: BLE001
            stats.record_failed("inventory", item.get("_id"), e)

    # Images → S3Asset
    for old_key in char.get("images", []):
        try:
            new_key = old_key  # preserve the key path
            s3.copy_object(old_key, new_key)

            asset = _build_s3_asset(
                old_key=old_key,
                new_key=new_key,
                s3=s3,
                character_id=new_char.id,
                company_id=company.id,
                uploaded_by=new_char.user_creator_id,
            )
            await _save(asset, dry_run=dry_run)
            if not dry_run:
                new_char.asset_ids.append(asset.id)
            stats.record_created("s3_asset")
        except Exception as e:  # noqa: BLE001
            stats.record_failed("s3_asset", old_key, e)

    # Save updated asset_ids back to character
    if char.get("images") and not dry_run:
        await new_char.save()


async def _migrate_characters(
    old_db: AsyncDatabase,
    all_characters: list[dict[str, Any]],
    guild_id: int,
    company: Any,
    id_map: IDMap,
    s3: S3Migrator,
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
        stats: Migration statistics tracker.
        dry_run: If True, don't write to the new database or copy S3 objects.
    """
    # Created on first use to avoid empty campaigns when all chars have campaigns
    uncategorized_campaign_id: PydanticObjectId | None = None

    for char in all_characters:
        old_char_id = str(char["_id"])

        # Determine campaign_id — fall back to an uncategorized campaign if needed
        old_campaign_ref = char.get("campaign")
        if old_campaign_ref:
            campaign_id = id_map.get("campaign", str(old_campaign_ref))
            if campaign_id is None:
                stats.record_skipped("character", f"campaign not migrated: {old_char_id}")
                continue
        else:
            # Create the uncategorized placeholder campaign once per company
            if uncategorized_campaign_id is None:
                uncat = Campaign(name="Uncategorized", company_id=company.id)
                await _save(uncat, dry_run=dry_run)
                uncategorized_campaign_id = uncat.id
                stats.record_created("campaign")
            campaign_id = uncategorized_campaign_id

        try:
            new_char = transform_character(char, id_map, company.id, campaign_id, guild_id)
            await _save(new_char, dry_run=dry_run)
            id_map.add("character", old_char_id, new_char.id)
            stats.record_created("character")
            logger.info("Character %s → %s", old_char_id, new_char.id)

            await _migrate_character_contents(
                old_db, char, new_char, company, s3, stats, dry_run=dry_run
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
    """Migrate roll statistics as DiceRoll documents for a guild.

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
            dice_roll = transform_roll_statistic(stat_doc, id_map, guild_id)
            if dice_roll is None:
                stats.record_skipped("diceroll", f"no company: {stat_doc.get('_id')}")
                continue

            # Best-effort trait_ids lookup from old trait names
            old_trait_names = stat_doc.get("traits", [])
            if old_trait_names:
                for tname in old_trait_names:
                    matched = await Trait.find_one(
                        Trait.name == tname.title(), Trait.is_custom == False
                    )
                    if matched:
                        dice_roll.trait_ids.append(matched.id)

            await _save(dice_roll, dry_run=dry_run)
            stats.record_created("diceroll")
        except Exception as e:  # noqa: BLE001
            stats.record_failed("diceroll", stat_doc.get("_id"), e)


async def migrate_guild(
    guild: dict[str, Any],
    old_db: AsyncDatabase,
    id_map: IDMap,
    s3: S3Migrator,
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
        stats: Migration statistics tracker.
        dry_run: If True, don't write to new DB or copy S3 objects.
    """
    guild_id = guild["_id"]
    logger.info("Migrating guild: %s (id=%s)", guild.get("name"), guild_id)

    # Step 1: Guild → Company
    try:
        company = transform_guild_to_company(guild)
        await _save(company, dry_run=dry_run)
        id_map.add("guild", guild_id, company.id)
        stats.record_created("company")
        logger.info("Guild %s → Company %s", guild_id, company.id)
    except Exception as e:  # noqa: BLE001
        stats.record_failed("company", guild_id, e)
        return

    # Step 2: Users
    all_characters = await read_characters(old_db, guild_id)
    old_users = await read_users(old_db)
    user_ids_in_company = await _migrate_users(
        guild, old_users, all_characters, company, id_map, stats, dry_run=dry_run
    )

    # Step 2b: Backfill Company.user_ids
    if user_ids_in_company and not dry_run:
        company.user_ids = user_ids_in_company
        await company.save()

    # Step 3: Campaigns + Books + Chapters
    await _migrate_campaigns(old_db, guild_id, company, id_map, stats, dry_run=dry_run)

    # Step 4: Backfill User Campaign Experience
    await _backfill_campaign_experience(old_users, guild_id, id_map, stats, dry_run=dry_run)

    # Step 5: Characters + Traits + Inventory + Images
    await _migrate_characters(
        old_db, all_characters, guild_id, company, id_map, s3, stats, dry_run=dry_run
    )

    # Step 6: Notes
    await _migrate_notes(old_db, guild_id, id_map, stats, dry_run=dry_run)

    # Step 7: RollStatistic → DiceRoll
    await _migrate_dice_rolls(old_db, guild_id, id_map, stats, dry_run=dry_run)


async def _migrate_trait(
    trait_doc: dict[str, Any],
    character_id: PydanticObjectId,
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
    trait_name = trait_doc.get("name", "")
    trait_value = trait_doc.get("value", 0)

    # Remap known trait names before matching
    trait_name = _TRAIT_NAME_REMAPS.get(trait_name.lower(), trait_name)

    # Try to find an existing trait blueprint by name (case-insensitive via title())
    existing_trait = await Trait.find_one(
        Trait.name == trait_name.title(),
        Trait.is_custom == False,
    )

    if existing_trait:
        char_trait = CharacterTrait(
            character_id=character_id,
            trait=existing_trait,
            value=trait_value,
        )
        await _save(char_trait, dry_run=dry_run)
        stats.record_created("trait_matched")
    else:
        # Log unmatched trait name for review
        logger.debug("Unmatched trait: %s (character_id=%s)", trait_name, character_id)
        _unmatched_traits.append(trait_name)

        # Create a custom trait blueprint when no standard trait matches
        from vapi.db.models.constants.sheet_section import CharSheetSection
        from vapi.db.models.constants.trait_categories import TraitCategory

        section = await CharSheetSection.find_one()
        category = await TraitCategory.find_one()

        if section and category:
            custom_trait = Trait(
                name=(
                    trait_name.title()
                    if len(trait_name) >= MIN_TRAIT_NAME_LENGTH
                    else f"{trait_name}___"
                ),
                is_custom=True,
                custom_for_character_id=character_id,
                sheet_section_id=section.id,
                parent_category_id=category.id,
                max_value=trait_doc.get("max_value", 5),
            )
            await _save(custom_trait, dry_run=dry_run)

            char_trait = CharacterTrait(
                character_id=character_id,
                trait=custom_trait,
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


def _build_s3_asset(
    old_key: str,
    new_key: str,
    s3: S3Migrator,
    character_id: PydanticObjectId,
    company_id: PydanticObjectId,
    uploaded_by: PydanticObjectId,
) -> Any:
    """Build an S3Asset document for a migrated image.

    Args:
        old_key: The old S3 key.
        new_key: The new S3 key.
        s3: The S3 migrator instance.
        character_id: The new Character ID.
        company_id: The new Company ID.
        uploaded_by: The uploader's user ID.

    Returns:
        An S3Asset instance (not yet saved).
    """
    import mimetypes
    from pathlib import Path

    from vapi.constants import AssetParentType, AssetType
    from vapi.db.models.aws import S3Asset

    filename = Path(old_key).name
    mime_type_guess, _ = mimetypes.guess_type(old_key)
    mime_type = mime_type_guess or "application/octet-stream"

    return S3Asset(
        asset_type=AssetType.IMAGE,
        mime_type=mime_type,
        original_filename=filename,
        parent_type=AssetParentType.CHARACTER,
        parent_id=character_id,
        company_id=company_id,
        uploaded_by=uploaded_by,
        s3_key=new_key,
        s3_bucket=settings.aws.s3_bucket_name,
        public_url=s3.build_public_url(new_key),
    )


def _write_unmatched_traits() -> None:
    """Write unmatched trait names to a file for review."""
    unmatched_path = Path("scripts/migrate/unmatched_traits.txt")
    sorted_unique = sorted(set(_unmatched_traits))
    unmatched_path.write_text("\n".join(sorted_unique) + "\n")
    logger.info(
        "Wrote %d unique unmatched trait names to %s",
        len(sorted_unique),
        unmatched_path,
    )


async def run_migration(*, dry_run: bool) -> None:
    """Run the full migration pipeline.

    Args:
        dry_run: If True, log all operations without writing.
    """
    prefix = "[DRY RUN] " if dry_run else ""
    logger.info("%sStarting migration", prefix)

    # Connect to databases
    new_client = await connect_new_db()
    old_client, old_db = await connect_old_db()

    id_map = IDMap()
    stats = MigrationStats()
    s3 = S3Migrator(dry_run=dry_run)

    # Clean up S3 objects from any previous migration run
    s3.cleanup_previous_run()

    try:
        guilds = await read_guilds(old_db)
        logger.info("%sFound %d guilds to migrate", prefix, len(guilds))

        for guild in guilds:
            await migrate_guild(guild, old_db, id_map, s3, stats, dry_run=dry_run)

        # Save S3 asset log for future cleanup
        s3.save_log()

        # Write unmatched traits to file for review
        if _unmatched_traits:
            _write_unmatched_traits()

    finally:
        await old_client.close()
        await new_client.close()

    stats.print_summary(dry_run=dry_run)


def main() -> None:
    """Parse arguments and run the migration."""
    parser = argparse.ArgumentParser(description="Migrate old Valentina DB to Valentina Noir")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log all operations without writing to the new database or copying S3 objects",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    asyncio.run(run_migration(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
