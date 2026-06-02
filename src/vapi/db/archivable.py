"""Single source of truth for models in the archive / restore / purge lifecycle.

PURGE_MODELS lists the *top of each FK-CASCADE tree*, the only rows the purge
job must hard-delete, since Postgres ON DELETE CASCADE removes their children
(traits, specialties, class attributes, inventory, campaign experiences).

archivable_models() discovers *every* model that can carry an archive_batch_id,
used by restore to sweep an entire batch regardless of depth.
"""

from typing import TYPE_CHECKING

from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.character import Character, CharacterInventory
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.diceroll import DiceRoll
from vapi.db.sql_models.dictionary import DictionaryTerm
from vapi.db.sql_models.notes import Note
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import User

if TYPE_CHECKING:
    from tortoise.models import Model

# Child-first ordering respects FK dependencies for hard deletes. S3Asset is
# handled separately by the purge job (AWS object deletion) and is intentionally
# excluded here.
PURGE_MODELS: list[type["Model"]] = [
    DiceRoll,
    DictionaryTerm,
    Note,
    QuickRoll,
    CharacterInventory,
    Character,
    CampaignChapter,
    CampaignBook,
    Campaign,
    CharacterConcept,
    User,
    Company,
]


def archivable_models() -> list[type["Model"]]:
    """Return every registered model that carries an archive_batch_id column.

    Discovered dynamically from the Tortoise registry so a new archivable model
    is covered by restore without editing a hand-maintained list.
    """
    from tortoise import Tortoise

    return [
        model
        for app in Tortoise.apps.values()
        for model in app.values()
        if "archive_batch_id" in model._meta.fields_map  # noqa: SLF001
    ]
