"""Models."""

from .audit_log import AuditLog
from .aws import S3Asset
from .campaign import Campaign, CampaignBase, CampaignBook, CampaignChapter
from .character import Character, CharacterInventory, CharacterTrait
from .character_concept import CharacterConcept
from .company import Company
from .constants.advantage_category import AdvantageCategory
from .constants.character_classes import (
    CharacterClassConstant,
    HunterEdge,
    HunterEdgePerk,
    VampireClan,
    WerewolfAuspice,
    WerewolfGift,
    WerewolfRite,
    WerewolfTribe,
)
from .constants.sheet_section import CharSheetSection
from .constants.trait import Trait
from .constants.trait_categories import TraitCategory
from .developer import Developer
from .diceroll import DiceRoll
from .dictionary import DictionaryTerm
from .notes import Note
from .quickroll import QuickRoll
from .user import User

__all__ = (
    "AdvantageCategory",
    "AuditLog",
    "Campaign",
    "CampaignBase",
    "CampaignBook",
    "CampaignChapter",
    "CharSheetSection",
    "Character",
    "CharacterClassConstant",
    "CharacterConcept",
    "CharacterInventory",
    "CharacterTrait",
    "Company",
    "Developer",
    "DiceRoll",
    "DictionaryTerm",
    "HunterEdge",
    "HunterEdgePerk",
    "Note",
    "QuickRoll",
    "S3Asset",
    "Trait",
    "TraitCategory",
    "User",
    "VampireClan",
    "WerewolfAuspice",
    "WerewolfGift",
    "WerewolfRite",
    "WerewolfTribe",
)

init_beanie_models = [
    S3Asset,
    AdvantageCategory,
    AuditLog,
    Campaign,
    CampaignBook,
    CampaignChapter,
    CharSheetSection,
    Character,
    CharacterClassConstant,
    CharacterConcept,
    CharacterInventory,
    CharacterTrait,
    Company,
    Developer,
    DiceRoll,
    DictionaryTerm,
    HunterEdge,
    HunterEdgePerk,
    Note,
    QuickRoll,
    Trait,
    TraitCategory,
    User,
    VampireClan,
    WerewolfAuspice,
    WerewolfGift,
    WerewolfRite,
    WerewolfTribe,
]
