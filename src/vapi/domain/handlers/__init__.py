"""Domain handlers."""

from .archive_handlers import (
    ArchiveContext,
    CampaignArchiveHandler,
    CharacterArchiveHandler,
    CompanyArchiveHandler,
    UserArchiveHandler,
    archive_book,
    archive_campaign,
    archive_chapter,
    archive_character,
    archive_company,
    archive_user,
    cascade_archive_user,
)
from .character_autogeneration.handler import CharacterAutogenerationHandler
from .restore_handlers import restore_archive_batch

__all__ = (
    "ArchiveContext",
    "CampaignArchiveHandler",
    "CharacterArchiveHandler",
    "CharacterAutogenerationHandler",
    "CompanyArchiveHandler",
    "UserArchiveHandler",
    "archive_book",
    "archive_campaign",
    "archive_chapter",
    "archive_character",
    "archive_company",
    "archive_user",
    "cascade_archive_user",
    "restore_archive_batch",
)
