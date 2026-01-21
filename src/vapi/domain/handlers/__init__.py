"""Domain handlers."""

from .archive_handlers import (
    CampaignArchiveHandler,
    CharacterArchiveHandler,
    CompanyArchiveHandler,
    UserArchiveHandler,
)
from .character_autogeneration.handler import CharacterAutogenerationHandler

__all__ = (
    "CampaignArchiveHandler",
    "CharacterArchiveHandler",
    "CharacterAutogenerationHandler",
    "CompanyArchiveHandler",
    "UserArchiveHandler",
)
