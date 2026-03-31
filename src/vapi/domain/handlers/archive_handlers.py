"""Archive handlers.

Used to handle the archiving of various models and their associated data.
"""

import asyncio
import logging

from beanie import PydanticObjectId
from beanie.operators import In, Set

from vapi.constants import AssetParentType
from vapi.db.models import (
    Campaign,
    CampaignBook,
    CampaignChapter,
    Character,
    CharacterConcept,
    CharacterInventory,
    Company,
    DiceRoll,
    DictionaryTerm,
    Note,
    QuickRoll,
    S3Asset,
    Trait,
    User,
)

logger = logging.getLogger("vapi")


async def archive_s3_assets(
    s3_asset_type: AssetParentType, object_ids: list[PydanticObjectId]
) -> int:
    """Archive all S3 assets associated with the campaign."""
    updated_s3_assets = await S3Asset.find(
        S3Asset.parent_type == s3_asset_type,
        In(S3Asset.parent_id, object_ids),
    ).update_many(Set({S3Asset.is_archived: True}))

    return updated_s3_assets.modified_count  # type: ignore [union-attr]


class CampaignArchiveHandler:
    """Campaign archive handler."""

    def __init__(self, campaign: Campaign) -> None:
        """Initialize the campaign archive handler."""
        self.campaign = campaign

    async def handle(self) -> None:
        """Handle the archiving of the campaign."""
        campaign_books = await CampaignBook.find(
            CampaignBook.campaign_id == self.campaign.id
        ).to_list()
        book_ids = [b.id for b in campaign_books]

        campaign_chapters = await CampaignChapter.find(
            In(CampaignChapter.book_id, book_ids)
        ).to_list()
        chapter_ids = [c.id for c in campaign_chapters]

        await CampaignChapter.find(In(CampaignChapter.book_id, book_ids)).update_many(
            Set({CampaignChapter.is_archived: True})
        )
        await CampaignBook.find(CampaignBook.campaign_id == self.campaign.id).update_many(
            Set({CampaignBook.is_archived: True})
        )

        s3_counts = await asyncio.gather(
            archive_s3_assets(AssetParentType.CAMPAIGN_CHAPTER, chapter_ids),
            archive_s3_assets(AssetParentType.CAMPAIGN_BOOK, book_ids),
            archive_s3_assets(AssetParentType.CAMPAIGN, [self.campaign.id]),
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

        num_s3_assets_archived = await archive_s3_assets(
            AssetParentType.CHARACTER, [self.character.id]
        )

        custom_traits = await Trait.find(
            Trait.custom_for_character_id == self.character.id
        ).update_many(Set({Trait.is_archived: True}))

        inventory_items = await CharacterInventory.find(
            CharacterInventory.character_id == self.character.id
        ).update_many(Set({CharacterInventory.is_archived: True}))

        msg = "Archive character"
        logger.debug(
            msg,
            extra={
                "component": "character_archive_handler",
                "character_id": self.character.id,
                "s3_assets_archived": num_s3_assets_archived,
                "custom_traits_archived": custom_traits.modified_count,  # type: ignore [union-attr]
                "inventory_items_archived": inventory_items.modified_count,  # type: ignore [union-attr]
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

        num_quickrolls_archived = await QuickRoll.find(
            QuickRoll.user_id == self.user.id
        ).update_many(Set({QuickRoll.is_archived: True}))

        num_s3_assets_archived = await archive_s3_assets(AssetParentType.USER, [self.user.id])

        for character in await Character.find(Character.user_player_id == self.user.id).to_list():
            await CharacterArchiveHandler(character=character).handle()

        msg = "Archive user"
        logger.debug(
            msg,
            extra={
                "component": "user_archive_handler",
                "user_id": self.user.id,
                "num_quickrolls_archived": num_quickrolls_archived.modified_count,  # type: ignore [union-attr]
                "num_s3_assets_archived": num_s3_assets_archived,
            },
        )


class CompanyArchiveHandler:
    """Company archive handler."""

    def __init__(self, company: Company) -> None:
        """Initialize the company archive handler."""
        self.company = company

    async def _archive_other_models(self) -> None:
        """Archive other models associated with the company."""
        for model in [Note, DictionaryTerm, CharacterConcept, DiceRoll, S3Asset]:
            archived = await model.find(
                model.company_id == self.company.id,
                model.is_archived == False,
            ).update_many(Set({model.is_archived: True}))

            msg = f"Archive {model.__name__}"
            logger.debug(
                msg,
                extra={
                    "component": "company_archive_handler",
                    "company_id": self.company.id,
                    "num_archived": archived.modified_count,  # type: ignore [union-attr]
                },
            )

    async def handle(self) -> None:
        """Handle the archiving of a company."""
        msg = "Archive company and all associated data."
        logger.debug(
            msg, extra={"component": "company_archive_handler", "company_id": self.company.id}
        )

        for campaign in await Campaign.find(Campaign.company_id == self.company.id).to_list():
            await CampaignArchiveHandler(campaign=campaign).handle()

        for character in await Character.find(Character.company_id == self.company.id).to_list():
            await CharacterArchiveHandler(character=character).handle()

        for user in await User.find(User.company_id == self.company.id).to_list():
            await UserArchiveHandler(user=user).handle()

        await self._archive_other_models()

        self.company.is_archived = True
        await self.company.save()

        msg = msg + " Completed"
        logger.debug(
            msg,
            extra={"component": "company_archive_handler", "company_id": self.company.id},
        )
