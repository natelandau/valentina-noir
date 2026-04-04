"""Transform old database documents into new Tortoise ORM model instances."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any
from uuid import UUID as StdUUID  # noqa: N811

from vapi.constants import (
    CharacterClass,
    CharacterStatus,
    CharacterType,
    DiceSize,
    GameVersion,
    InventoryItemType,
    PermissionManageCampaign,
    PermissionsFreeTraitChanges,
    PermissionsGrantXP,
    RollResultType,
    UserRole,
)
from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.character import (
    Character,
    CharacterInventory,
    HunterAttributes,
    MageAttributes,
    VampireAttributes,
    WerewolfAttributes,
)
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.company import Company, CompanySettings
from vapi.db.sql_models.diceroll import DiceRoll, DiceRollResult
from vapi.db.sql_models.notes import Note
from vapi.db.sql_models.user import CampaignExperience, User

if TYPE_CHECKING:
    from uuid import UUID

    from tortoise.models import Model as TortoiseModel

    from .id_map import IDMap

logger = logging.getLogger("migrate")

# Minimum length for optional string fields in the new schema
MIN_STR_LENGTH = 3

# Minimum length for name parts (first/last name fragments)
MIN_NAME_PART_LENGTH = 2


def _safe_str(value: str | None, min_length: int = MIN_STR_LENGTH) -> str | None:
    """Return the string if it meets minimum length, otherwise None.

    Args:
        value: The string value to validate.
        min_length: Minimum required length.

    Returns:
        The string if valid, None otherwise.
    """
    if value is None:
        return None
    return value if len(value) >= min_length else None


def _pad_name(value: str, min_length: int = MIN_STR_LENGTH) -> str:
    """Pad a required name field to meet minimum length.

    Args:
        value: The name to pad.
        min_length: Minimum required length.

    Returns:
        The name padded with underscores if needed.
    """
    while len(value) < min_length:
        value += "_"
    return value


def _parse_generation(value: str | None) -> int | None:
    """Parse a generation string to int.

    Handles formats like '13', '13th', 'Thin-Blood'.

    Args:
        value: The generation string.

    Returns:
        The generation as int, or None if unparsable.
    """
    if value is None:
        return None
    match = re.search(r"(\d+)", value)
    return int(match.group(1)) if match else None


def _map_permissions(old_permissions: dict[str, Any]) -> CompanySettings:
    """Map old Guild permissions to new CompanySettings.

    Args:
        old_permissions: The old permissions dict.

    Returns:
        CompanySettings with best-effort permission mapping.
    """
    settings = CompanySettings()

    manage_traits = old_permissions.get("manage_traits", "")
    if "WITHIN_24_HOURS" in str(manage_traits).upper():
        settings.permission_free_trait_changes = PermissionsFreeTraitChanges.WITHIN_24_HOURS
    elif "STORYTELLER" in str(manage_traits).upper():
        settings.permission_free_trait_changes = PermissionsFreeTraitChanges.STORYTELLER

    grant_xp = old_permissions.get("grant_xp", "")
    if "PLAYER" in str(grant_xp).upper():
        settings.permission_grant_xp = PermissionsGrantXP.PLAYER
    elif "STORYTELLER" in str(grant_xp).upper():
        settings.permission_grant_xp = PermissionsGrantXP.STORYTELLER

    manage_campaigns = old_permissions.get("manage_campaigns", "")
    if "STORYTELLER" in str(manage_campaigns).upper():
        settings.permission_manage_campaign = PermissionManageCampaign.STORYTELLER

    return settings


def transform_guild_to_company(guild: dict[str, Any]) -> tuple[Company, CompanySettings]:
    """Transform an old Guild document into a new Company and CompanySettings.

    The CompanySettings is returned without ``company_id`` set; the caller must
    wire it after saving the Company.

    Args:
        guild: The old Guild document as a dict.

    Returns:
        A tuple of (Company, CompanySettings) instances (not yet saved).
    """
    permissions = guild.get("permissions", {})
    company = Company(
        name=_pad_name(guild["name"][:50]),
        email=f"guild-{guild['_id']}@migrated.example.com",
    )
    settings = _map_permissions(permissions)
    return company, settings


def transform_user(
    user: dict[str, Any],
    guild: dict[str, Any],
    company_id: UUID,
) -> User:
    """Transform an old User document into a new User instance.

    Args:
        user: The old User document as a dict.
        guild: The old Guild document for role assignment.
        company_id: The new Company ID.

    Returns:
        A new User instance (not yet saved).
    """
    old_id = user["_id"]
    name = user.get("name")

    # Determine name_first and name_last
    if name and len(name) >= MIN_NAME_PART_LENGTH:
        parts = name.split(" ", 1)
        name_first = parts[0] if len(parts[0]) >= MIN_NAME_PART_LENGTH else f"Discord_{old_id}"
        name_last = parts[1] if len(parts) > 1 and len(parts[1]) >= MIN_NAME_PART_LENGTH else None
    else:
        name_first = f"Discord_{old_id}"
        name_last = None

    # Determine username
    username = name if name and len(name) >= MIN_STR_LENGTH else f"discord_{old_id}"

    # Determine role from guild admin/storyteller lists
    administrators = guild.get("administrators", [])
    storytellers = guild.get("storytellers", [])
    if old_id in administrators:
        role = UserRole.ADMIN
    elif old_id in storytellers:
        role = UserRole.STORYTELLER
    else:
        role = UserRole.PLAYER

    return User(
        name_first=name_first,
        name_last=name_last,
        username=username,
        email=f"{old_id}@migrated.example.com",
        role=role,
        company_id=company_id,
        discord_profile={"id": str(old_id), "username": name},
    )


def transform_campaign(
    campaign: dict[str, Any],
    company_id: UUID,
) -> Campaign:
    """Transform an old Campaign document into a new Campaign instance.

    Args:
        campaign: The old Campaign document as a dict.
        company_id: The new Company ID.

    Returns:
        A new Campaign instance (not yet saved).
    """
    return Campaign(
        name=_pad_name(campaign["name"][:50]),
        description=_safe_str(campaign.get("description")),
        desperation=campaign.get("desperation", 0),
        danger=campaign.get("danger", 0),
        company_id=company_id,
    )


def transform_campaign_book(
    book: dict[str, Any],
    campaign_id: UUID,
) -> CampaignBook:
    """Transform an old CampaignBook into a new CampaignBook instance.

    Args:
        book: The old CampaignBook document as a dict.
        campaign_id: The new Campaign ID.

    Returns:
        A new CampaignBook instance (not yet saved).
    """
    description = book.get("description_long") or book.get("description_short")
    return CampaignBook(
        name=_pad_name(book["name"][:50]),
        description=_safe_str(description),
        number=book.get("number", 1),
        campaign_id=campaign_id,
    )


def transform_campaign_chapter(
    chapter: dict[str, Any],
    book_id: UUID,
) -> CampaignChapter:
    """Transform an old CampaignBookChapter into a new CampaignChapter instance.

    Args:
        chapter: The old chapter document as a dict.
        book_id: The new CampaignBook ID.

    Returns:
        A new CampaignChapter instance (not yet saved).
    """
    description = chapter.get("description_long") or chapter.get("description_short")
    return CampaignChapter(
        name=_pad_name(chapter["name"][:50]),
        description=_safe_str(description),
        number=chapter.get("number", 1),
        book_id=book_id,
    )


def build_campaign_experience_list(
    old_experience: dict[str, Any],
    id_map: IDMap,
) -> list[CampaignExperience]:
    """Build a list of CampaignExperience objects from old dict format.

    The returned instances do not have ``user_id`` set; the caller must wire
    that after creation.

    Args:
        old_experience: Old campaign_experience dict keyed by campaign string ID.
        id_map: The ID map for campaign ID lookups.

    Returns:
        List of CampaignExperience objects with remapped campaign IDs.
    """
    experiences: list[CampaignExperience] = []
    for old_campaign_id, xp_data in old_experience.items():
        new_campaign_id = id_map.get("campaign", str(old_campaign_id))
        if new_campaign_id is None:
            logger.warning("Skipping campaign XP for unmapped campaign: %s", old_campaign_id)
            continue

        if isinstance(xp_data, dict):
            experiences.append(
                CampaignExperience(
                    campaign_id=new_campaign_id,
                    xp_current=xp_data.get("xp_current", 0),
                    xp_total=xp_data.get("xp_total", 0),
                    cool_points=xp_data.get("cool_points", 0),
                )
            )
    return experiences


def _map_character_class(old_class_name: str) -> CharacterClass:
    """Map old character class enum name to new CharacterClass.

    Args:
        old_class_name: The old char_class_name string.

    Returns:
        The corresponding CharacterClass enum value.
    """
    mapping: dict[str, CharacterClass] = {
        "VAMPIRE": CharacterClass.VAMPIRE,
        "WEREWOLF": CharacterClass.WEREWOLF,
        "MAGE": CharacterClass.MAGE,
        "HUNTER": CharacterClass.HUNTER,
        "GHOUL": CharacterClass.GHOUL,
        "MORTAL": CharacterClass.MORTAL,
    }
    return mapping.get(old_class_name.upper(), CharacterClass.MORTAL)


def _map_character_type(old_char: dict[str, Any]) -> CharacterType:
    """Determine CharacterType from old boolean type flags.

    Args:
        old_char: The old character document.

    Returns:
        The corresponding CharacterType.
    """
    if old_char.get("type_storyteller"):
        return CharacterType.STORYTELLER
    if old_char.get("type_developer"):
        return CharacterType.DEVELOPER
    if old_char.get("type_player"):
        return CharacterType.PLAYER
    return CharacterType.NPC


def _resolve_character_users(
    char: dict[str, Any],
    id_map: IDMap,
    guild_id: int,
) -> tuple[UUID | None, UUID | None]:
    """Resolve creator and player user IDs for a character.

    Falls back to the first available user in the guild when the original
    creator or owner cannot be found in the ID map.

    Args:
        char: The old Character document as a dict.
        id_map: The ID map for user ID lookups.
        guild_id: The old guild ID for user lookup.

    Returns:
        A tuple of (user_creator_id, user_player_id).
    """
    user_creator_id = id_map.get("user", (char.get("user_creator"), guild_id))
    user_player_id = id_map.get("user", (char.get("user_owner"), guild_id))

    if user_creator_id is None:
        all_users = id_map.get_all("user")
        user_creator_id = next(
            (
                uid
                for key, uid in all_users.items()
                if isinstance(key, tuple) and key[1] == guild_id
            ),
            None,
        )
    if user_player_id is None:
        user_player_id = user_creator_id

    return user_creator_id, user_player_id


async def _resolve_character_class_fks(
    char: dict[str, Any],
) -> tuple[UUID | None, UUID | None, UUID | None]:
    """Resolve clan, tribe, and auspice FK IDs from character class name strings.

    Queries the database for matching constant records. Logs a warning and
    returns None for any name that cannot be resolved.

    Args:
        char: The old Character document as a dict.

    Returns:
        A tuple of (clan_id, tribe_id, auspice_id).
    """
    clan_id = None
    clan_name = _safe_str(char.get("clan_name"))
    if clan_name:
        clan_obj = await VampireClan.filter(name__iexact=clan_name).first()
        if clan_obj:
            clan_id = StdUUID(str(clan_obj.id))
        else:
            logger.warning("Vampire clan not found: %s", clan_name)

    tribe_id = None
    tribe_name = _safe_str(char.get("tribe"))
    if tribe_name:
        tribe_obj = await WerewolfTribe.filter(name__iexact=tribe_name).first()
        if tribe_obj:
            tribe_id = StdUUID(str(tribe_obj.id))
        else:
            logger.warning("Werewolf tribe not found: %s", tribe_name)

    auspice_id = None
    auspice_name = _safe_str(char.get("auspice"))
    if auspice_name:
        auspice_obj = await WerewolfAuspice.filter(name__iexact=auspice_name).first()
        if auspice_obj:
            auspice_id = StdUUID(str(auspice_obj.id))
        else:
            logger.warning("Werewolf auspice not found: %s", auspice_name)

    return clan_id, tribe_id, auspice_id


async def transform_character(
    char: dict[str, Any],
    id_map: IDMap,
    company_id: UUID,
    campaign_id: UUID,
    guild_id: int,
) -> tuple[Character, list[TortoiseModel]]:
    """Transform an old Character document into a new Character and attribute models.

    The returned attribute models do not have ``character_id`` set; the caller
    must wire that after saving the Character.

    Args:
        char: The old Character document as a dict.
        id_map: The ID map for user ID lookups.
        company_id: The new Company ID.
        campaign_id: The new Campaign ID.
        guild_id: The old guild ID for user lookup.

    Returns:
        A tuple of (Character, list of attribute model instances).
    """
    user_creator_id, user_player_id = _resolve_character_users(char, id_map, guild_id)
    character_class = _map_character_class(char.get("char_class_name", "MORTAL"))
    clan_id, tribe_id, auspice_id = await _resolve_character_class_fks(char)

    character = Character(
        name_first=_pad_name(char.get("name_first", "Unknown")),
        name_last=_pad_name(char.get("name_last", "Unknown")),
        name_nick=_safe_str(char.get("name_nick")),
        character_class=character_class,
        type=_map_character_type(char),
        game_version=GameVersion.V4,
        status=CharacterStatus.ALIVE if char.get("is_alive", True) else CharacterStatus.DEAD,
        starting_points=char.get("freebie_points", 0),
        age=char.get("age"),
        biography=_safe_str(char.get("bio")),
        demeanor=_safe_str(char.get("demeanor")),
        nature=_safe_str(char.get("nature")),
        user_creator_id=user_creator_id,
        user_player_id=user_player_id,
        company_id=company_id,
        campaign_id=campaign_id,
    )

    # Build attribute models (without character_id -- caller wires after save)
    related_models: list[TortoiseModel] = [
        VampireAttributes(
            clan_id=clan_id,
            generation=_parse_generation(char.get("generation")),
            sire=_safe_str(char.get("sire")),
        ),
        WerewolfAttributes(
            tribe_id=tribe_id,
            auspice_id=auspice_id,
        ),
    ]

    if character_class == CharacterClass.MAGE:
        tradition = _safe_str(char.get("tradition"))
        if tradition:
            related_models.append(MageAttributes(tradition=tradition))

    if character_class == CharacterClass.HUNTER:
        creed = _safe_str(char.get("creed_name"))
        if creed:
            related_models.append(HunterAttributes(creed=creed))

    return character, related_models


def transform_inventory_item(
    item: dict[str, Any],
    character_id: UUID,
) -> CharacterInventory:
    """Transform an old InventoryItem into a new CharacterInventory instance.

    Args:
        item: The old InventoryItem document.
        character_id: The new Character ID.

    Returns:
        A new CharacterInventory instance (not yet saved).
    """
    type_mapping: dict[str, InventoryItemType] = {
        "BOOK": InventoryItemType.BOOK,
        "CONSUMABLE": InventoryItemType.CONSUMABLE,
        "ENCHANTED": InventoryItemType.ENCHANTED,
        "EQUIPMENT": InventoryItemType.EQUIPMENT,
        "WEAPON": InventoryItemType.WEAPON,
    }
    item_type = type_mapping.get(str(item.get("type", "")).upper(), InventoryItemType.OTHER)

    return CharacterInventory(
        character_id=character_id,
        name=item.get("name", "Unknown Item"),
        description=_safe_str(item.get("description")),
        type=item_type,
    )


def transform_note(
    note: dict[str, Any],
    id_map: IDMap,
    guild_id: int | None,
) -> Note | None:
    """Transform an old Note document into a new Note instance.

    Args:
        note: The old Note document as a dict.
        id_map: The ID map for parent and user ID lookups.
        guild_id: The old guild ID for company lookup.

    Returns:
        A new Note instance, or None if the note should be skipped.
    """
    text = note.get("text", "")
    if len(text) < MIN_STR_LENGTH:
        logger.warning("Skipping note with text too short: %s", note.get("_id"))
        return None

    title = text[:50].strip()
    if len(title) < MIN_STR_LENGTH:
        title = "Migrated Note"

    # Determine company_id
    effective_guild_id = note.get("guild_id") or guild_id
    company_id = id_map.get("guild", effective_guild_id) if effective_guild_id else None
    if company_id is None:
        logger.warning("Skipping note with no resolvable company: %s", note.get("_id"))
        return None

    # Determine parent attachment
    parent_id = str(note.get("parent_id", ""))
    parent_type = id_map.find_entity_type(parent_id)

    new_note = Note(
        title=title,
        content=text,
        company_id=company_id,
    )

    if parent_type == "campaign":
        new_note.campaign_id = id_map.get("campaign", parent_id)
    elif parent_type == "book":
        new_note.book_id = id_map.get("book", parent_id)
    elif parent_type == "chapter":
        new_note.chapter_id = id_map.get("chapter", parent_id)
    elif parent_type == "character":
        new_note.character_id = id_map.get("character", parent_id)

    # Map user
    created_by = note.get("created_by")
    if created_by is not None and effective_guild_id is not None:
        user_id = id_map.get("user", (created_by, effective_guild_id))
        if user_id:
            new_note.user_id = user_id

    return new_note


def _map_roll_result_type(old_result: str) -> RollResultType:
    """Map old roll result type to new enum.

    Args:
        old_result: The old result type string.

    Returns:
        The corresponding RollResultType.
    """
    mapping: dict[str, RollResultType] = {
        "SUCCESS": RollResultType.SUCCESS,
        "FAILURE": RollResultType.FAILURE,
        "BOTCH": RollResultType.BOTCH,
        "CRITICAL": RollResultType.CRITICAL,
    }
    return mapping.get(str(old_result).upper(), RollResultType.OTHER)


def transform_roll_statistic(
    stat: dict[str, Any],
    id_map: IDMap,
    guild_id: int,
) -> tuple[DiceRoll, DiceRollResult] | None:
    """Transform an old RollStatistic into a new DiceRoll and DiceRollResult.

    The DiceRollResult is returned without ``dice_roll_id`` set; the caller must
    wire it after saving the DiceRoll.

    Args:
        stat: The old RollStatistic document.
        id_map: The ID map for user, character, campaign lookups.
        guild_id: The old guild ID.

    Returns:
        A tuple of (DiceRoll, DiceRollResult), or None if company lookup fails.
    """
    company_id = id_map.get("guild", guild_id)
    if company_id is None:
        return None

    result_type = _map_roll_result_type(stat.get("result", "OTHER"))

    # Map user ID
    old_user_id = stat.get("user")
    user_id = id_map.get("user", (old_user_id, guild_id)) if old_user_id else None

    # Map character ID
    old_char_id = stat.get("character")
    character_id = id_map.get("character", str(old_char_id)) if old_char_id else None

    # Map campaign ID
    old_campaign_id = stat.get("campaign")
    campaign_id = id_map.get("campaign", str(old_campaign_id)) if old_campaign_id else None

    dice_roll = DiceRoll(
        difficulty=stat.get("difficulty"),
        dice_size=DiceSize.D10,
        num_dice=stat.get("pool", 1),
        user_id=user_id,
        character_id=character_id,
        campaign_id=campaign_id,
        company_id=company_id,
    )

    # Override date_created from old date_rolled
    if stat.get("date_rolled"):
        dice_roll.date_created = stat["date_rolled"]

    dice_roll_result = DiceRollResult(
        total_result=None,
        total_result_type=result_type,
        total_result_humanized=result_type.value.title(),
        total_dice_roll=[],
        player_roll=[],
        desperation_roll=[],
    )

    return dice_roll, dice_roll_result
