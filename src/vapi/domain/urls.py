"""Centralized URL definitions with composable, hierarchical paths.

Each resource builds upon its parent resource, creating a clear hierarchy
and ensuring consistency across the API. Changes to parent paths automatically
propagate to all child resources.

All URL constants represent complete, fully-qualified paths from the root.
Controllers reference these complete paths directly without controller-level base paths.
"""

from vapi.constants import URL_ROOT_PATH


class GlobalAdmin:
    """Global admin management endpoints."""

    BASE = f"{URL_ROOT_PATH}/admin"
    DEVELOPERS = f"{BASE}/developers"
    DEVELOPER_DETAIL = f"{DEVELOPERS}/{{developer_id:str}}"
    DEVELOPER_CREATE = DEVELOPERS
    DEVELOPER_UPDATE = DEVELOPER_DETAIL
    DEVELOPER_DELETE = DEVELOPER_DETAIL
    DEVELOPER_NEW_KEY = f"{DEVELOPER_DETAIL}/new-key"
    DEVELOPER_COMPANY_PERMISSIONS = (
        f"{DEVELOPER_DETAIL}/company-permission/{{company_id:str}}/{{permission:str}}"
    )


class Developers:
    """Developer resource endpoints."""

    BASE = f"{URL_ROOT_PATH}/developers"
    ME = f"{BASE}/me"
    NEW_KEY = f"{ME}/new-key"
    UPDATE = ME


class Companies:
    """Company resource endpoints."""

    BASE = f"{URL_ROOT_PATH}/companies"
    LIST = BASE
    DETAIL = f"{BASE}/{{company_id:str}}"
    CREATE = BASE
    UPDATE = DETAIL
    DELETE = DETAIL
    STATISTICS = f"{DETAIL}/statistics"
    DEVELOPER_UPDATE = f"{DETAIL}/update-developer"
    DEVELOPER_DELETE = f"{DETAIL}/delete-developer"


class Users:
    """User resource endpoints (within a company context)."""

    BASE = f"{Companies.DETAIL}/users"
    LIST = BASE
    DETAIL = f"{BASE}/{{user_id:str}}"
    CREATE = BASE
    UPDATE = DETAIL
    DELETE = DETAIL

    # User assets
    ASSETS = f"{DETAIL}/assets"
    ASSET_UPLOAD = f"{ASSETS}/upload"
    ASSET_DETAIL = f"{ASSETS}/{{asset_id:str}}"
    ASSET_DELETE = ASSET_DETAIL

    STATISTICS = f"{DETAIL}/statistics"

    # User experience
    EXPERIENCE_BASE = f"{DETAIL}/experience"
    EXPERIENCE_CAMPAIGN = f"{EXPERIENCE_BASE}/{{campaign_id:str}}"
    XP_ADD = f"{EXPERIENCE_BASE}/xp/add"
    XP_REMOVE = f"{EXPERIENCE_BASE}/xp/remove"
    CP_ADD = f"{EXPERIENCE_BASE}/cp/add"

    # User notes
    NOTES = f"{DETAIL}/notes"
    LIST_NOTES = NOTES
    NOTE_DETAIL = f"{NOTES}/{{note_id:str}}"
    NOTE_CREATE = NOTES
    NOTE_UPDATE = NOTE_DETAIL
    NOTE_DELETE = NOTE_DETAIL

    # User quickrolls
    QUICKROLLS = f"{DETAIL}/quickrolls"
    QUICKROLL_DETAIL = f"{QUICKROLLS}/{{quickroll_id:str}}"
    QUICKROLL_CREATE = QUICKROLLS
    QUICKROLL_UPDATE = QUICKROLL_DETAIL
    QUICKROLL_DELETE = QUICKROLL_DETAIL


class Campaigns:
    """Campaign resource endpoints."""

    BASE = f"{Users.DETAIL}/campaigns"
    LIST = BASE
    DETAIL = f"{BASE}/{{campaign_id:str}}"
    CREATE = BASE
    UPDATE = DETAIL
    DELETE = DETAIL
    STATISTICS = f"{DETAIL}/statistics"

    # Campaign assets
    ASSETS = f"{DETAIL}/assets"
    ASSET_UPLOAD = f"{ASSETS}/upload"
    ASSET_DETAIL = f"{ASSETS}/{{asset_id:str}}"
    ASSET_DELETE = ASSET_DETAIL

    # Campaign notes
    NOTES = f"{DETAIL}/notes"
    NOTE_DETAIL = f"{NOTES}/{{note_id:str}}"
    NOTE_CREATE = NOTES
    NOTE_UPDATE = NOTE_DETAIL
    NOTE_DELETE = NOTE_DETAIL

    # Campaign books
    BOOKS = f"{DETAIL}/books"
    BOOK_DETAIL = f"{BOOKS}/{{book_id:str}}"
    BOOK_CREATE = BOOKS
    BOOK_UPDATE = BOOK_DETAIL
    BOOK_DELETE = BOOK_DETAIL
    BOOK_NUMBER = f"{BOOK_DETAIL}/number"

    # Book notes
    BOOK_NOTES = f"{BOOK_DETAIL}/notes"
    BOOK_NOTE_DETAIL = f"{BOOK_NOTES}/{{note_id:str}}"
    BOOK_NOTE_CREATE = BOOK_NOTES
    BOOK_NOTE_UPDATE = BOOK_NOTE_DETAIL
    BOOK_NOTE_DELETE = BOOK_NOTE_DETAIL

    # Book assets
    BOOK_ASSETS = f"{BOOK_DETAIL}/assets"
    BOOK_ASSET_UPLOAD = f"{BOOK_ASSETS}/upload"
    BOOK_ASSET_DETAIL = f"{BOOK_ASSETS}/{{asset_id:str}}"
    BOOK_ASSET_DELETE = BOOK_ASSET_DETAIL

    # Chapters sub-resource (nested under books)
    CHAPTERS = f"{BOOK_DETAIL}/chapters"
    CHAPTER_DETAIL = f"{CHAPTERS}/{{chapter_id:str}}"
    CHAPTER_CREATE = CHAPTERS
    CHAPTER_UPDATE = CHAPTER_DETAIL
    CHAPTER_DELETE = CHAPTER_DETAIL
    CHAPTER_NUMBER = f"{CHAPTER_DETAIL}/number"

    # Chapter Notes
    CHAPTER_NOTES = f"{CHAPTER_DETAIL}/notes"
    CHAPTER_NOTE_DETAIL = f"{CHAPTER_NOTES}/{{note_id:str}}"
    CHAPTER_NOTE_CREATE = CHAPTER_NOTES
    CHAPTER_NOTE_UPDATE = CHAPTER_NOTE_DETAIL
    CHAPTER_NOTE_DELETE = CHAPTER_NOTE_DETAIL

    # Chapter assets
    CHAPTER_ASSETS = f"{CHAPTER_DETAIL}/assets"
    CHAPTER_ASSET_UPLOAD = f"{CHAPTER_ASSETS}/upload"
    CHAPTER_ASSET_DETAIL = f"{CHAPTER_ASSETS}/{{asset_id:str}}"
    CHAPTER_ASSET_DELETE = CHAPTER_ASSET_DETAIL


class Characters:
    """Character resource endpoints - all character-related URLs in one place."""

    BASE = f"{Campaigns.DETAIL}/characters"
    LIST = BASE
    CREATE = BASE
    DETAIL = f"{BASE}/{{character_id:str}}"
    UPDATE = DETAIL
    DELETE = DETAIL
    STATISTICS = f"{DETAIL}/statistics"

    # Character assets
    ASSETS = f"{DETAIL}/assets"
    ASSET_UPLOAD = f"{ASSETS}/upload"
    ASSET_DETAIL = f"{ASSETS}/{{asset_id:str}}"
    ASSET_DELETE = ASSET_DETAIL

    # Character RNG generation
    AUTOGENERATE = f"{BASE}/autogenerate"  # Used for storytellers to generate single characters
    CHARGEN_START = f"{BASE}/chargen/start"  # Used for players to start a chargen session
    CHARGEN_FINALIZE = f"{BASE}/chargen/finalize"

    # Notes sub-resource
    NOTES = f"{DETAIL}/notes"
    NOTE_DETAIL = f"{NOTES}/{{note_id:str}}"
    NOTE_CREATE = NOTES
    NOTE_UPDATE = NOTE_DETAIL
    NOTE_DELETE = NOTE_DETAIL

    # Character traits (kept here for visibility)
    TRAITS = f"{DETAIL}/traits"
    TRAIT_DETAIL = f"{TRAITS}/{{character_trait_id:str}}"
    TRAIT_DELETE = TRAIT_DETAIL
    TRAIT_UPDATE = TRAIT_DETAIL
    TRAIT_ASSIGN = f"{TRAITS}/assign"
    TRAIT_CREATE = f"{TRAITS}/create"
    TRAIT_INCREASE = f"{TRAIT_DETAIL}/increase"
    TRAIT_DECREASE = f"{TRAIT_DETAIL}/decrease"
    TRAIT_XP_PURCHASE = f"{TRAIT_DETAIL}/xp/purchase"
    TRAIT_XP_REFUND = f"{TRAIT_DETAIL}/xp/refund"
    TRAIT_STARTINGPOINTS_PURCHASE = f"{TRAIT_DETAIL}/startingpoints/purchase"
    TRAIT_STARTINGPOINTS_REFUND = f"{TRAIT_DETAIL}/startingpoints/refund"

    # Character inventory
    INVENTORY = f"{DETAIL}/inventory"
    INVENTORY_DETAIL = f"{INVENTORY}/{{inventory_item_id:str}}"
    INVENTORY_CREATE = INVENTORY
    INVENTORY_UPDATE = INVENTORY_DETAIL
    INVENTORY_DELETE = INVENTORY_DETAIL

    # Werewolf Gifts
    GIFTS = f"{DETAIL}/gifts"
    GIFT_DETAIL = f"{GIFTS}/{{werewolf_gift_id:str}}"
    GIFT_ADD = GIFT_DETAIL
    GIFT_REMOVE = GIFT_DETAIL

    # Werewolf Rites
    RITES = f"{DETAIL}/rites"
    RITE_DETAIL = f"{RITES}/{{werewolf_rite_id:str}}"
    RITE_ADD = RITE_DETAIL
    RITE_REMOVE = RITE_DETAIL

    # Hunter Edges
    EDGES = f"{DETAIL}/edges"
    EDGE_DETAIL = f"{EDGES}/{{hunter_edge_id:str}}"
    EDGE_ADD = EDGE_DETAIL
    EDGE_REMOVE = EDGE_DETAIL

    # Hunter Edge Perks (nested under edges)
    EDGE_PERKS = f"{EDGE_DETAIL}/perks"
    EDGE_PERK_DETAIL = f"{EDGE_PERKS}/{{hunter_edge_perk_id:str}}"
    EDGE_PERK_ADD = EDGE_PERK_DETAIL
    EDGE_PERK_REMOVE = EDGE_PERK_DETAIL


class CharacterBlueprints:
    """Character blueprints endpoints."""

    BASE = f"{Companies.DETAIL}/characterblueprint"
    TRAITS = f"{BASE}/traits"
    TRAIT_DETAIL = f"{TRAITS}/{{trait_id:str}}"

    # Sections by game version
    SECTIONS = f"{BASE}/{{game_version:str}}/sections"
    SECTION_DETAIL = f"{SECTIONS}/{{section_id:str}}"

    # Categories within sections
    CATEGORIES = f"{SECTION_DETAIL}/categories"
    CATEGORY_DETAIL = f"{CATEGORIES}/{{category_id:str}}"

    # Traits within categories
    CATEGORY_TRAITS = f"{CATEGORY_DETAIL}/traits"

    # Classes, Concepts, and class specific options
    CONCEPTS = f"{BASE}/concepts"
    CONCEPT_DETAIL = f"{CONCEPTS}/{{concept_id:str}}"
    VAMPIRE_CLANS = f"{BASE}/vampire-clans"
    VAMPIRE_CLAN_DETAIL = f"{VAMPIRE_CLANS}/{{vampire_clan_id:str}}"
    WEREWOLF_TRIBES = f"{BASE}/werewolf-tribes"
    WEREWOLF_TRIBE_DETAIL = f"{WEREWOLF_TRIBES}/{{werewolf_tribe_id:str}}"
    WEREWOLF_AUSPICES = f"{BASE}/werewolf-auspices"
    WEREWOLF_AUSPIE_DETAIL = f"{WEREWOLF_AUSPICES}/{{werewolf_auspice_id:str}}"
    WEREWOLF_GIFTS = f"{BASE}/werewolf-gifts"
    WEREWOLF_GIFT_DETAIL = f"{WEREWOLF_GIFTS}/{{werewolf_gift_id:str}}"
    WEREWOLF_RITES = f"{BASE}/werewolf-rites"
    WEREWOLF_RITE_DETAIL = f"{WEREWOLF_RITES}/{{werewolf_rite_id:str}}"
    HUNTER_EDGES = f"{BASE}/hunter-edges"
    HUNTER_EDGE_DETAIL = f"{HUNTER_EDGES}/{{hunter_edge_id:str}}"
    HUNTER_EDGE_PERKS = f"{HUNTER_EDGE_DETAIL}/perks"
    HUNTER_EDGE_PERK_DETAIL = f"{HUNTER_EDGE_PERKS}/{{hunter_edge_perk_id:str}}"


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

    BASE = f"{Users.DETAIL}/dicerolls"
    LIST = BASE
    DETAIL = f"{BASE}/{{diceroll_id:str}}"
    CREATE = BASE
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
