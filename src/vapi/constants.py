"""Constants."""

from enum import Enum, StrEnum
from pathlib import Path
from typing import Final

PROJECT_ROOT_PATH: Final[Path] = Path(__file__).parents[2].absolute()
MODULE_ROOT_PATH: Final[Path] = Path(__file__).parent.absolute()
ENVAR_PREFIX: Final[str] = "VAPI_"
MAX_NUM_DICE: Final[int] = 100  # maximum number of dice that can be rolled in a pool
URL_ROOT_PATH: Final[str] = "/api/v1"
AUTH_HEADER_KEY: Final[str] = "X-API-KEY"
EXCLUDE_FROM_RATE_LIMIT_KEY: Final[str] = "exclude_from_rate_limit"
COOL_POINT_VALUE: Final[int] = 10
MAX_DANGER: Final[int] = 5
MAX_DESPERATION: Final[int] = 5
IGNORE_RATE_LIMIT_HEADER_KEY: Final[str] = "X-Testing-Ignore-Rate-Limit"
IDEMPOTENCY_KEY_HEADER: Final[str] = "Idempotency-Key"
IDEMPOTENCY_TTL_SECONDS: Final[int] = 3600  # 1 hour
DEFAULT_CHARACTER_AUTGEN_XP_COST: Final[int] = 10
DEFAULT_CHARACTER_AUTGEN_NUM_CHOICES: Final[int] = 3
AWS_ONE_YEAR_CACHE_HEADER: Final[str] = "public, max-age=31536000, immutable"
AWS_ONE_DAY_CACHE_HEADER: Final[str] = "public, max-age=86400"
AWS_ONE_HOUR_CACHE_HEADER: Final[str] = "public, max-age=3600"


class CharacterClass(StrEnum):
    """Character class."""

    VAMPIRE = "VAMPIRE"
    WEREWOLF = "WEREWOLF"
    MAGE = "MAGE"
    HUNTER = "HUNTER"
    GHOUL = "GHOUL"
    MORTAL = "MORTAL"


class CharacterStatus(StrEnum):
    """Character status."""

    ALIVE = "ALIVE"
    DEAD = "DEAD"


class CharacterType(StrEnum):
    """Character type."""

    PLAYER = "PLAYER"
    NPC = "NPC"
    STORYTELLER = "STORYTELLER"
    DEVELOPER = "DEVELOPER"


class CompanyPermission(StrEnum):
    """Application permissions."""

    USER = "USER"
    ADMIN = "ADMIN"
    OWNER = "OWNER"
    REVOKE = "REVOKE"


class DiceSize(Enum):
    """Dice size."""

    D4 = 4
    D6 = 6
    D8 = 8
    D10 = 10
    D20 = 20
    D100 = 100


class GameVersion(StrEnum):
    """Game version."""

    V4 = "V4"
    V5 = "V5"


class InventoryItemType(StrEnum):
    """Inventory item type."""

    BOOK = "BOOK"
    CONSUMABLE = "CONSUMABLE"
    ENCHANTED = "ENCHANTED"
    EQUIPMENT = "EQUIPMENT"
    OTHER = "OTHER"
    WEAPON = "WEAPON"


class LogLevel(StrEnum):
    """Log level."""

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class PermissionsFreeTraitChanges(StrEnum):
    """Permissions for updating character trait values."""

    UNRESTRICTED = "UNRESTRICTED"  # Default
    WITHIN_24_HOURS = "WITHIN_24_HOURS"
    STORYTELLER = "STORYTELLER"


class PermissionsGrantXP(StrEnum):
    """Permissions for adding xp to a character."""

    UNRESTRICTED = "UNRESTRICTED"  # Default
    PLAYER = "PLAYER"
    STORYTELLER = "STORYTELLER"


class PermissionManageCampaign(StrEnum):
    """Permissions for managing a campaign."""

    UNRESTRICTED = "UNRESTRICTED"  # Default
    STORYTELLER = "STORYTELLER"


class RollResultType(StrEnum):
    """Enum for results of a roll."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    BOTCH = "BOTCH"
    CRITICAL = "CRITICAL"
    OTHER = "OTHER"


class SpecialtyType(StrEnum):
    """Specialty type."""

    ACTION = "ACTION"
    OTHER = "OTHER"
    PASSIVE = "PASSIVE"
    RITUAL = "RITUAL"
    SPELL = "SPELL"


class TraitModifyCurrency(StrEnum):
    """Currency options for modifying trait values."""

    NO_COST = "NO_COST"
    XP = "XP"
    STARTING_POINTS = "STARTING_POINTS"


class UserRole(StrEnum):
    """User role."""

    ADMIN = "ADMIN"
    STORYTELLER = "STORYTELLER"
    PLAYER = "PLAYER"


class WerewolfRenown(StrEnum):
    """Werewolf renown."""

    GLORY = "GLORY"
    HONOR = "HONOR"
    WISDOM = "WISDOM"


class HunterEdgeType(StrEnum):
    """Hunter edge type."""

    ASSETS = "ASSETS"
    APTITUDES = "APTITUDES"
    ENDOWMENTS = "ENDOWMENTS"


class HunterCreed(StrEnum):
    """Hunter creed."""

    ENTREPRENEURIAL = "ENTREPRENEURIAL"
    FAITHFUL = "FAITHFUL"
    INQUISITIVE = "INQUISITIVE"
    MARTIAL = "MARTIAL"
    UNDERGROUND = "UNDERGROUND"


class AssetType(StrEnum):
    """Asset type."""

    IMAGE = "image"
    TEXT = "text"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"
    ARCHIVE = "archive"
    OTHER = "other"


class AssetParentType(StrEnum):
    """S3 asset parent type.

    The values are the lowercase class name of the parent database model.
    """

    CHARACTER = "character"
    CAMPAIGN = "campaign"
    CAMPAIGN_BOOK = "campaignbook"
    CAMPAIGN_CHAPTER = "campaignchapter"
    USER = "user"
    COMPANY = "company"
    UNKNOWN = "unknown"
