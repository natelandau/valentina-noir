"""Domain controllers."""

from .assets import (
    BookAssetsController,
    CampaignAssetsController,
    ChapterAssetsController,
    CharacterAssetsController,
    UserAssetsController,
)
from .campaign import (
    CampaignBookController,
    CampaignChapterController,
    CampaignController,
)
from .character.controllers import CharacterController
from .character_blueprint.controllers import CharacterBlueprintSectionController
from .character_generation.controllers import CharacterGenerationController
from .character_inventory.controllers import CharacterInventoryController
from .character_specials.hunter_controller import HunterSpecialsController
from .character_specials.werewolf_controller import WerewolfSpecialsController
from .character_trait.controllers import CharacterTraitController
from .company.controllers import CompanyController
from .developer.controllers import DeveloperController
from .dicerolls.controllers import DiceRollController
from .dictionary.controllers import DictionaryTermController
from .global_admin.controllers import GlobalAdminController
from .notes import (
    CampaignBookNoteController,
    CampaignChapterNoteController,
    CampaignNoteController,
    CharacterNoteController,
    UserNoteController,
)
from .oauth.controllers import OAuth2Controller
from .options.controllers import OptionsController
from .statistics.controllers import StatisticsController
from .system.controllers import SystemController
from .user import ExperienceController, QuickRollController, UserController

__all__ = (
    "BookAssetsController",
    "CampaignAssetsController",
    "CampaignBookController",
    "CampaignBookNoteController",
    "CampaignChapterController",
    "CampaignChapterNoteController",
    "CampaignController",
    "CampaignNoteController",
    "ChapterAssetsController",
    "CharacterAssetsController",
    "CharacterBlueprintSectionController",
    "CharacterController",
    "CharacterGenerationController",
    "CharacterInventoryController",
    "CharacterNoteController",
    "CharacterTraitController",
    "CompanyController",
    "DeveloperController",
    "DiceRollController",
    "DictionaryTermController",
    "ExperienceController",
    "GlobalAdminController",
    "HunterSpecialsController",
    "OAuth2Controller",
    "OptionsController",
    "QuickRollController",
    "StatisticsController",
    "SystemController",
    "UserAssetsController",
    "UserController",
    "UserNoteController",
    "WerewolfSpecialsController",
)
