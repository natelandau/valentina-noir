"""Models."""

from .audit_log import AuditLog
from .aws import S3Asset
from .campaign import Campaign, CampaignBase, CampaignBook, CampaignChapter
from .character import Character, CharacterInventory, CharacterTrait
from .character_concept import CharacterConcept
from .chargen_session import ChargenSession
from .company import Company
from .constants.character_classes import (
    CharacterClassConstant,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)
from .constants.sheet_section import CharSheetSection
from .constants.trait import Trait
from .constants.trait_categories import TraitCategory
from .constants.trait_subcategories import TraitSubcategory
from .developer import Developer
from .diceroll import DiceRoll
from .dictionary import DictionaryTerm
from .notes import Note
from .quickroll import QuickRoll
from .user import User

__all__ = (
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
    "ChargenSession",
    "Company",
    "Developer",
    "DiceRoll",
    "DictionaryTerm",
    "Note",
    "QuickRoll",
    "S3Asset",
    "Trait",
    "TraitCategory",
    "TraitSubcategory",
    "User",
    "VampireClan",
    "WerewolfAuspice",
    "WerewolfTribe",
)

# This is imported into the init database function and must list all models that are used in the application.
init_beanie_models = [
    S3Asset,
    AuditLog,
    Campaign,
    CampaignBook,
    CampaignChapter,
    CharSheetSection,
    Character,
    CharacterClassConstant,
    CharacterConcept,
    ChargenSession,
    CharacterInventory,
    CharacterTrait,
    Company,
    Developer,
    DiceRoll,
    DictionaryTerm,
    Note,
    QuickRoll,
    Trait,
    TraitCategory,
    TraitSubcategory,
    User,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
]
