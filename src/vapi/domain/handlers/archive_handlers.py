"""Archive handlers.

Used to handle the archiving of various models and their associated data.
"""

import asyncio
import logging
from uuid import UUID

from vapi.db.sql_models.aws import S3Asset
from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.character import Character, CharacterInventory
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.diceroll import DiceRoll
from vapi.db.sql_models.dictionary import DictionaryTerm
from vapi.db.sql_models.notes import Note
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import User

logger = logging.getLogger("vapi")


async def archive_s3_assets(fk_field: str, object_ids: list[UUID]) -> int:
    """Archive all S3 assets matching the given FK field and IDs."""
    return await S3Asset.filter(
        **{f"{fk_field}__in": object_ids},
        is_archived=False,
    ).update(is_archived=True)


class CampaignArchiveHandler:
    """Campaign archive handler."""

    def __init__(self, campaign: Campaign) -> None:
        """Initialize the campaign archive handler."""
        self.campaign = campaign

    async def handle(self) -> None:
        """Handle the archiving of the campaign."""
        campaign_books = await CampaignBook.filter(campaign_id=self.campaign.id)
        book_ids = [b.id for b in campaign_books]

        campaign_chapters = await CampaignChapter.filter(book_id__in=book_ids)
        chapter_ids = [c.id for c in campaign_chapters]

        await CampaignChapter.filter(book_id__in=book_ids).update(is_archived=True)
        await CampaignBook.filter(campaign_id=self.campaign.id).update(is_archived=True)

        s3_counts = await asyncio.gather(
            archive_s3_assets("chapter_id", chapter_ids),
            archive_s3_assets("book_id", book_ids),
            archive_s3_assets("campaign_id", [self.campaign.id]),
        )
        num_s3_assets = sum(s3_counts)

        self.campaign.is_archived = True
        await self.campaign.save()

        logger.debug(
            "Archive campaign",
            extra={
                "component": "campaign_archive_handler",
                "campaign_id": self.campaign.id,
                "s3_assets_archived": num_s3_assets,
                "campaign_books_archived": len(campaign_books),
                "campaign_chapters_archived": len(campaign_chapters),
            },
        )


class CharacterArchiveHandler:
    """Character archive handler."""

    def __init__(self, character: Character) -> None:
        """Initialize the character archive handler."""
        self.character = character

    async def handle(self) -> None:
        """Handle the archiving of the character."""
        self.character.is_archived = True
        await self.character.save()

        num_s3_assets_archived = await archive_s3_assets("character_id", [self.character.id])

        custom_traits_archived = await Trait.filter(
            custom_for_character_id=self.character.id,
        ).update(is_archived=True)

        inventory_items_archived = await CharacterInventory.filter(
            character_id=self.character.id,
        ).update(is_archived=True)

        logger.debug(
            "Archive character",
            extra={
                "component": "character_archive_handler",
                "character_id": self.character.id,
                "s3_assets_archived": num_s3_assets_archived,
                "custom_traits_archived": custom_traits_archived,
                "inventory_items_archived": inventory_items_archived,
            },
        )


class UserArchiveHandler:
    """User archive handler."""

    def __init__(self, user: User) -> None:
        """Initialize the user archive handler."""
        self.user = user

    async def handle(self) -> None:
        """Handle the archiving of the user."""
        self.user.is_archived = True
        await self.user.save()

        num_quickrolls_archived = await QuickRoll.filter(
            user_id=self.user.id,
        ).update(is_archived=True)

        num_s3_assets_archived = await archive_s3_assets("user_parent_id", [self.user.id])

        for character in await Character.filter(user_player_id=self.user.id):
            await CharacterArchiveHandler(character=character).handle()

        logger.debug(
            "Archive user",
            extra={
                "component": "user_archive_handler",
                "user_id": self.user.id,
                "num_quickrolls_archived": num_quickrolls_archived,
                "num_s3_assets_archived": num_s3_assets_archived,
            },
        )


async def archive_user_cascade(user_id: UUID) -> None:
    """Archive data owned by a user without touching the User record itself.

    The Tortoise UserService archives the User record, then calls this
    function to cascade archival to QuickRoll, S3Asset, and Character.

    Args:
        user_id: The user's UUID.
    """
    await QuickRoll.filter(user_id=user_id).update(is_archived=True)
    await archive_s3_assets("user_parent_id", [user_id])

    for character in await Character.filter(user_player_id=user_id):
        await CharacterArchiveHandler(character=character).handle()


class CompanyArchiveHandler:
    """Company archive handler."""

    def __init__(self, company: Company) -> None:
        """Initialize the company archive handler."""
        self.company = company

    async def _archive_other_models(self) -> None:
        """Archive other models associated with the company."""
        for model in [Note, DictionaryTerm, CharacterConcept, DiceRoll, S3Asset]:
            archived = await model.filter(
                company_id=self.company.id,
                is_archived=False,
            ).update(is_archived=True)

            logger.debug(
                "Archive %s",
                model.__name__,
                extra={
                    "component": "company_archive_handler",
                    "company_id": self.company.id,
                    "num_archived": archived,
                },
            )

    async def handle(self) -> None:
        """Handle the archiving of a company."""
        logger.debug(
            "Archive company and all associated data.",
            extra={"component": "company_archive_handler", "company_id": self.company.id},
        )

        for campaign in await Campaign.filter(company_id=self.company.id):
            await CampaignArchiveHandler(campaign=campaign).handle()

        for character in await Character.filter(company_id=self.company.id):
            await CharacterArchiveHandler(character=character).handle()

        for user in await User.filter(company_id=self.company.id):
            await UserArchiveHandler(user=user).handle()

        await self._archive_other_models()

        self.company.is_archived = True
        await self.company.save()

        logger.debug(
            "Archive company and all associated data. Completed",
            extra={"component": "company_archive_handler", "company_id": self.company.id},
        )
