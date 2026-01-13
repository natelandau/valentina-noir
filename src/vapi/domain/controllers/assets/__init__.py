"""Assets controllers."""

from .book_assets import BookAssetsController
from .campaign_assets import CampaignAssetsController
from .chapter_assets import ChapterAssetsController
from .character_assets import CharacterAssetsController
from .user_assets import UserAssetsController

__all__ = (
    "BookAssetsController",
    "CampaignAssetsController",
    "ChapterAssetsController",
    "CharacterAssetsController",
    "UserAssetsController",
)
