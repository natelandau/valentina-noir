"""Constants."""

from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Final

PROJECT_ROOT_PATH: Final[Path] = Path(__file__).parents[2].absolute()
MODULE_ROOT_PATH: Final[Path] = Path(__file__).parent.absolute()
ENVAR_PREFIX: Final[str] = "VAPI_"
MAX_NUM_DICE: Final[int] = 100  # maximum number of dice that can be rolled in a pool
URL_ROOT_PATH: Final[str] = "/api/v1"
DOCS_URL: Final[str] = "https://docs.valentina-noir.com"
AUTH_HEADER_KEY: Final[str] = "X-API-KEY"
ON_BEHALF_OF_HEADER_KEY: Final[str] = "On-Behalf-Of"
EXCLUDE_FROM_RATE_LIMIT_KEY: Final[str] = "exclude_from_rate_limit"

# Maps each public log field name to (target, reader_key).
# target is "request", "response", "synthetic", or "scope". This table is the
# single source of truth: the settings catalog and the middleware's field
# routing and output renaming are all derived from it. For "request"/"response"
# the reader_key is the litestar extractor field; only `body` and `headers`
# collide across sides, so only those carry a request_/response_ prefix. For
# "scope" the reader_key selects an ASGI-scope reader in the logging middleware.
LOG_FIELD_ROUTING: Final[dict[str, tuple[str, str]]] = {
    "path": ("request", "path"),
    "method": ("request", "method"),
    "query": ("request", "query"),
    "path_params": ("request", "path_params"),
    "client": ("request", "client"),
    "content_type": ("request", "content_type"),
    "scheme": ("request", "scheme"),
    "cookies": ("request", "cookies"),
    "status_code": ("response", "status_code"),
    "request_body": ("request", "body"),
    "request_headers": ("request", "headers"),
    "response_body": ("response", "body"),
    "response_headers": ("response", "headers"),
    "duration_ms": ("synthetic", "duration_ms"),
    "request_id": ("scope", "request_id"),
    "developer_id": ("scope", "developer_id"),
    "operation_id": ("scope", "operation_id"),
    "idempotency_key": ("scope", "idempotency_key"),
    "acting_user_id": ("scope", "acting_user_id"),
    "error_detail": ("scope", "error_detail"),
    "error_type": ("scope", "error_type"),
    "invalid_parameters": ("scope", "invalid_parameters"),
}
LOG_FIELDS_CATALOG: Final[frozenset[str]] = frozenset(LOG_FIELD_ROUTING)

COOL_POINT_VALUE: Final[int] = 10
MAX_BULK_TRAIT_ASSIGN: Final[int] = 200
MAX_DANGER: Final[int] = 5
MAX_DESPERATION: Final[int] = 5
IGNORE_RATE_LIMIT_HEADER_KEY: Final[str] = "X-Testing-Ignore-Rate-Limit"
IDEMPOTENCY_KEY_HEADER: Final[str] = "Idempotency-Key"
IDEMPOTENCY_KEY_STATE_KEY: Final[str] = "idempotency_key"
IDEMPOTENCY_TTL_SECONDS: Final[int] = 3600  # 1 hour
IDEMPOTENCY_MAX_CACHED_BODY_BYTES: Final[int] = 1024 * 1024  # 1 MB
AUDIT_LOG_RETENTION_DAYS: Final[int] = 365
REQUEST_ID_HEADER: Final[str] = "X-Request-Id"
REQUEST_ID_STATE_KEY: Final[str] = "request_id"
ERROR_DETAIL_STATE_KEY: Final[str] = "error_detail"
ERROR_TYPE_STATE_KEY: Final[str] = "error_type"
INVALID_PARAMETERS_STATE_KEY: Final[str] = "invalid_parameters"
DEFAULT_CHARACTER_AUTGEN_XP_COST: Final[int] = 10
DEFAULT_CHARACTER_AUTGEN_NUM_CHOICES: Final[int] = 3
AWS_ONE_YEAR_CACHE_HEADER: Final[str] = "public, max-age=31536000, immutable"
AWS_ONE_DAY_CACHE_HEADER: Final[str] = "public, max-age=86400"
AWS_ONE_HOUR_CACHE_HEADER: Final[str] = "public, max-age=3600"
BACKUP_S3_PREFIX: Final[str] = "db_backups/"
RECOUP_XP_SESSION_LENGTH: Final[int] = (
    3600  # seconds (1 hour); used for WITHIN_SESSION recoup floor TTL
)


class BlueprintTraitOrderBy(StrEnum):
    """Trait sort."""

    NAME = "NAME"
    SHEET = "SHEET"


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


class DiceSize(IntEnum):
    """Dice size."""

    D4 = 4
    D6 = 6
    D8 = 8
    D10 = 10
    D20 = 20
    D100 = 100


class DictionarySourceType(StrEnum):
    """Source types for seeded dictionary terms."""

    TRAIT = "trait"
    CLAN = "clan"
    TRIBE = "tribe"
    AUSPICE = "auspice"
    TRAIT_SUBCATEGORY = "trait_subcategory"


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


class PermissionsRecoupXP(StrEnum):
    """Permissions for lowering a character trait value using the XP currency."""

    UNRESTRICTED = "UNRESTRICTED"
    DENIED = "DENIED"  # Default
    WITHIN_SESSION = "WITHIN_SESSION"


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
    UNAPPROVED = "UNAPPROVED"
    DEACTIVATED = "DEACTIVATED"


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


class AuditOperation(StrEnum):
    """Audit log operation type."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class AuditEntityType(StrEnum):
    """Audit log entity type."""

    ASSET = "ASSET"
    BOOK = "BOOK"
    CAMPAIGN = "CAMPAIGN"
    CHAPTER = "CHAPTER"
    CHARACTER = "CHARACTER"
    CHARACTER_INVENTORY = "CHARACTER_INVENTORY"
    CHARACTER_TRAIT = "CHARACTER_TRAIT"
    CHARGEN_SESSION = "CHARGEN_SESSION"
    COMPANY = "COMPANY"
    DEVELOPER = "DEVELOPER"
    DICTIONARY_TERM = "DICTIONARY_TERM"
    EXPERIENCE = "EXPERIENCE"
    NOTE = "NOTE"
    QUICKROLL = "QUICKROLL"
    USER = "USER"
