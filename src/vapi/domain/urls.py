"""Centralized URL definitions with composable, hierarchical paths.

Each resource builds upon its parent resource, creating a clear hierarchy
and ensuring consistency across the API. Changes to parent paths automatically
propagate to all child resources.

All URL constants represent complete, fully-qualified paths from the root.
Controllers reference these complete paths directly without controller-level base paths.
"""

from vapi.constants import URL_ROOT_PATH


def _note_urls(base: str) -> tuple[str, str, str, str, str]:
    """Return the (list, detail, create, update, delete) note paths for a parent's notes base.

    Notes are a uniform sub-resource on every parent (user, campaign, book, chapter,
    character); this keeps the five paths in lock-step from a single base string.
    """
    detail = f"{base}/{{note_id:str}}"
    return base, detail, base, detail, detail


def _asset_urls(base: str) -> tuple[str, str, str, str]:
    """Return the (list, upload, detail, delete) asset paths for a parent's assets base.

    Assets are a uniform sub-resource on every parent; this keeps the four paths in
    lock-step from a single base string.
    """
    detail = f"{base}/{{asset_id:str}}"
    return base, f"{base}/upload", detail, detail


class GlobalAdmin:
    """Global admin management endpoints."""

    BASE = f"{URL_ROOT_PATH}/admin"
    DEVELOPERS = f"{BASE}/developers"
    DEVELOPER_DETAIL = f"{DEVELOPERS}/{{developer_id:str}}"
    DEVELOPER_CREATE = DEVELOPERS
    DEVELOPER_UPDATE = DEVELOPER_DETAIL
    DEVELOPER_DELETE = DEVELOPER_DETAIL
    DEVELOPER_NEW_KEY = f"{DEVELOPER_DETAIL}/new-key"
    DEVELOPER_AUDIT_LOGS = f"{DEVELOPER_DETAIL}/audit-logs"
    USERS = f"{BASE}/users"
    USER_DETAIL = f"{USERS}/{{user_id:str}}"
    USER_CREATE = USERS
    USER_UPDATE = USER_DETAIL
    USER_DELETE = USER_DETAIL
    LOGS = f"{BASE}/logs"
    LOGS_DOWNLOAD = f"{LOGS}/download"


class Developers:
    """Developer resource endpoints."""

    BASE = f"{URL_ROOT_PATH}/developers"
    ME = f"{BASE}/me"
    NEW_KEY = f"{ME}/new-key"
    UPDATE = ME


class UserLookup:
    """Cross-company user lookup endpoints."""

    LOOKUP = f"{URL_ROOT_PATH}/users/lookup"


class Companies:
    """Company resource endpoints."""

    BASE = f"{URL_ROOT_PATH}/companies"
    LIST = BASE
    DETAIL = f"{BASE}/{{company_id:str}}"
    CREATE = BASE
    UPDATE = DETAIL
    DELETE = DETAIL
    STATISTICS = f"{DETAIL}/statistics"
    DEVELOPER_ACCESS = f"{DETAIL}/access"
    AUDIT_LOGS = f"{DETAIL}/audit-logs"


class Users:
    """User resource endpoints (within a company context)."""

    BASE = f"{Companies.DETAIL}/users"
    LIST = BASE
    DETAIL = f"{BASE}/{{user_id:str}}"
    CREATE = BASE
    UPDATE = DETAIL
    DELETE = DETAIL

    # Unapproved user management
    UNAPPROVED_LIST = f"{BASE}/unapproved"
    APPROVE = f"{DETAIL}/approve"
    DENY = f"{DETAIL}/deny"

    # Account management
    MERGE = f"{BASE}/merge"

    # User assets
    ASSETS, ASSET_UPLOAD, ASSET_DETAIL, ASSET_DELETE = _asset_urls(f"{DETAIL}/assets")

    # User avatar
    AVATAR = f"{DETAIL}/avatar"

    STATISTICS = f"{DETAIL}/statistics"

    # User experience
    EXPERIENCE_BASE = f"{DETAIL}/experience"
    EXPERIENCE_CAMPAIGN = f"{EXPERIENCE_BASE}/{{campaign_id:str}}"
    XP_ADD = f"{EXPERIENCE_BASE}/xp/add"
    XP_REMOVE = f"{EXPERIENCE_BASE}/xp/remove"
    CP_ADD = f"{EXPERIENCE_BASE}/cp/add"

    # User notes
    NOTES, NOTE_DETAIL, NOTE_CREATE, NOTE_UPDATE, NOTE_DELETE = _note_urls(f"{DETAIL}/notes")
    LIST_NOTES = NOTES

    # User quickrolls
    QUICKROLLS = f"{DETAIL}/quickrolls"
    QUICKROLL_DETAIL = f"{QUICKROLLS}/{{quickroll_id:str}}"
    QUICKROLL_CREATE = QUICKROLLS
    QUICKROLL_UPDATE = QUICKROLL_DETAIL
    QUICKROLL_DELETE = QUICKROLL_DETAIL


class Identity:
    """Verified identity resolution endpoints."""

    IDENTIFY = f"{Companies.DETAIL}/auth/identify"
    LINK = f"{Users.DETAIL}/identities"
    UNLINK = f"{LINK}/{{provider:str}}"


class Campaigns:
    """Campaign resource endpoints."""

    BASE = f"{Companies.DETAIL}/campaigns"
    LIST = BASE
    DETAIL = f"{BASE}/{{campaign_id:str}}"
    CREATE = BASE
    UPDATE = DETAIL
    DELETE = DETAIL
    STATISTICS = f"{DETAIL}/statistics"

    # Campaign assets
    ASSETS, ASSET_UPLOAD, ASSET_DETAIL, ASSET_DELETE = _asset_urls(f"{DETAIL}/assets")

    # Campaign notes
    NOTES, NOTE_DETAIL, NOTE_CREATE, NOTE_UPDATE, NOTE_DELETE = _note_urls(f"{DETAIL}/notes")

    # Campaign books
    BOOKS = f"{DETAIL}/books"
    BOOK_DETAIL = f"{BOOKS}/{{book_id:str}}"
    BOOK_CREATE = BOOKS
    BOOK_UPDATE = BOOK_DETAIL
    BOOK_DELETE = BOOK_DETAIL
    BOOK_NUMBER = f"{BOOK_DETAIL}/number"

    # Book notes
    BOOK_NOTES, BOOK_NOTE_DETAIL, BOOK_NOTE_CREATE, BOOK_NOTE_UPDATE, BOOK_NOTE_DELETE = _note_urls(
        f"{BOOK_DETAIL}/notes"
    )

    # Book assets
    BOOK_ASSETS, BOOK_ASSET_UPLOAD, BOOK_ASSET_DETAIL, BOOK_ASSET_DELETE = _asset_urls(
        f"{BOOK_DETAIL}/assets"
    )

    # Chapters sub-resource (nested under books)
    CHAPTERS = f"{BOOK_DETAIL}/chapters"
    CHAPTER_DETAIL = f"{CHAPTERS}/{{chapter_id:str}}"
    CHAPTER_CREATE = CHAPTERS
    CHAPTER_UPDATE = CHAPTER_DETAIL
    CHAPTER_DELETE = CHAPTER_DETAIL
    CHAPTER_NUMBER = f"{CHAPTER_DETAIL}/number"

    # Chapter Notes
    (
        CHAPTER_NOTES,
        CHAPTER_NOTE_DETAIL,
        CHAPTER_NOTE_CREATE,
        CHAPTER_NOTE_UPDATE,
        CHAPTER_NOTE_DELETE,
    ) = _note_urls(f"{CHAPTER_DETAIL}/notes")

    # Chapter assets
    CHAPTER_ASSETS, CHAPTER_ASSET_UPLOAD, CHAPTER_ASSET_DETAIL, CHAPTER_ASSET_DELETE = _asset_urls(
        f"{CHAPTER_DETAIL}/assets"
    )


class Characters:
    """Character resource endpoints - all character-related URLs in one place."""

    BASE = f"{Companies.DETAIL}/characters"
    LIST = BASE
    CREATE = BASE
    DETAIL = f"{BASE}/{{character_id:str}}"
    UPDATE = DETAIL
    DELETE = DETAIL
    STATISTICS = f"{DETAIL}/statistics"
    FULL_SHEET = f"{DETAIL}/full-sheet"
    FULL_SHEET_CATEGORY = f"{FULL_SHEET}/categories/{{category_id:str}}"

    # Character assets
    ASSETS, ASSET_UPLOAD, ASSET_DETAIL, ASSET_DELETE = _asset_urls(f"{DETAIL}/assets")

    # Character RNG generation
    AUTOGENERATE = f"{BASE}/autogenerate"  # Used for storytellers to generate single characters
    CHARGEN_START = f"{BASE}/chargen/start"  # Used for players to start a chargen session
    CHARGEN_FINALIZE = f"{BASE}/chargen/finalize"
    CHARGEN_SESSIONS = f"{BASE}/chargen/sessions"
    CHARGEN_SESSION_DETAIL = f"{CHARGEN_SESSIONS}/{{session_id:str}}"

    # Notes sub-resource
    NOTES, NOTE_DETAIL, NOTE_CREATE, NOTE_UPDATE, NOTE_DELETE = _note_urls(f"{DETAIL}/notes")

    # Character traits
    TRAITS = f"{DETAIL}/traits"
    TRAIT_DETAIL = f"{TRAITS}/{{character_trait_id:str}}"
    TRAIT_DELETE = TRAIT_DETAIL
    TRAIT_UPDATE = TRAIT_DETAIL
    TRAIT_ASSIGN = f"{TRAITS}/assign"
    TRAIT_CREATE = f"{TRAITS}/create"
    TRAIT_BULK_ASSIGN = f"{TRAITS}/bulk-assign"
    TRAIT_VALUE_OPTIONS = f"{TRAIT_DETAIL}/value-options"
    TRAIT_VALUE = f"{TRAIT_DETAIL}/value"

    # Character inventory
    INVENTORY = f"{DETAIL}/inventory"
    INVENTORY_DETAIL = f"{INVENTORY}/{{inventory_item_id:str}}"
    INVENTORY_CREATE = INVENTORY
    INVENTORY_UPDATE = INVENTORY_DETAIL
    INVENTORY_DELETE = INVENTORY_DETAIL


class CharacterBlueprints:
    """Character blueprints endpoints."""

    BASE = f"{Companies.DETAIL}/characterblueprint"
    TRAITS = f"{BASE}/traits"
    TRAIT_DETAIL = f"{TRAITS}/{{trait_id:str}}"

    # Sections
    SECTIONS = f"{BASE}/sections"
    SECTION_DETAIL = f"{SECTIONS}/{{section_id:str}}"

    # Categories
    CATEGORIES = f"{BASE}/categories"
    CATEGORY_DETAIL = f"{CATEGORIES}/{{category_id:str}}"

    # Subcategories
    SUBCATEGORIES = f"{BASE}/subcategories"
    SUBCATEGORY_DETAIL = f"{SUBCATEGORIES}/{{subcategory_id:str}}"

    # Classes, Concepts, and class specific options
    CONCEPTS = f"{BASE}/concepts"
    CONCEPT_DETAIL = f"{CONCEPTS}/{{concept_id:str}}"
    VAMPIRE_CLANS = f"{BASE}/vampire-clans"
    VAMPIRE_CLAN_DETAIL = f"{VAMPIRE_CLANS}/{{vampire_clan_id:str}}"
    WEREWOLF_TRIBES = f"{BASE}/werewolf-tribes"
    WEREWOLF_TRIBE_DETAIL = f"{WEREWOLF_TRIBES}/{{werewolf_tribe_id:str}}"
    WEREWOLF_AUSPICES = f"{BASE}/werewolf-auspices"
    WEREWOLF_AUSPICE_DETAIL = f"{WEREWOLF_AUSPICES}/{{werewolf_auspice_id:str}}"


class Dictionaries:
    """Dictionary/terminology endpoints."""

    BASE = f"{Companies.DETAIL}/dictionaries"
    LIST = BASE
    DETAIL = f"{BASE}/{{dictionary_term_id:str}}"
    CREATE = BASE
    UPDATE = DETAIL
    DELETE = DETAIL


class DiceRolls:
    """Gameplay and dice rolling endpoints."""

    BASE = f"{Companies.DETAIL}/dicerolls"
    LIST = BASE
    CREATE = BASE
    DETAIL = f"{BASE}/{{diceroll_id:str}}"
    QUICKROLL = f"{BASE}/quickroll"


class OAuth:
    """OAuth authentication endpoints."""

    BASE = "/oauth"
    DISCORD_LOGIN_REDIRECT = f"{BASE}/discord/{{user_id:str}}/login/redirect"
    DISCORD_LOGIN_URL = f"{BASE}/discord/{{user_id:str}}/login/"
    DISCORD_CALLBACK = f"{BASE}/discord/callback"
    DISCORD_REFRESH = f"{BASE}/discord/{{user_id:str}}/refresh/"


class Options:
    """Options endpoints."""

    LIST = f"{Companies.DETAIL}/options"


class System:
    """System administration endpoints."""

    BASE = f"{URL_ROOT_PATH}/system"
    HEALTH = f"{URL_ROOT_PATH}/health"
    METADATA = f"{URL_ROOT_PATH}/metadata"
    INFO = f"{BASE}/info"
