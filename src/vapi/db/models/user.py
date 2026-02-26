"""User model."""

from typing import Annotated, ClassVar

from beanie import PydanticObjectId
from pydantic import EmailStr, Field

from vapi.constants import COOL_POINT_VALUE, UserRole
from vapi.lib.exceptions import NotEnoughXPError

from .base import BaseDocument, HashedBaseModel


class DiscordOauth(HashedBaseModel):
    """Discord token model."""

    access_token: Annotated[str | None, Field(examples=["1234567890"])] = None
    refresh_token: Annotated[str | None, Field(examples=["1234567890"])] = None
    expires_in: Annotated[int | None, Field(examples=[1234567890])] = None
    expires_at: Annotated[int | None, Field(examples=[1234567890])] = None


class DiscordProfile(HashedBaseModel):
    """Discord profile model."""

    id: Annotated[str | None, Field(examples=["1234567890"])] = None
    username: Annotated[str | None, Field(examples=["John Doe"])] = None
    global_name: Annotated[str | None, Field(examples=["John Doe"])] = None
    avatar_id: Annotated[str | None, Field(examples=["1234567890"])] = None
    avatar_url: Annotated[str | None, Field(examples=["https://example.com/avatar.png"])] = None
    discriminator: Annotated[str | None, Field(examples=["1234"])] = None
    email: Annotated[str | None, Field(examples=["john.doe@example.com"])] = None
    verified: Annotated[bool | None, Field(examples=[True])] = None


class CampaignExperience(HashedBaseModel):
    """Dictionary representing a user's campaign experience as a subdocument attached to a User."""

    campaign_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])
    xp_current: Annotated[int, Field(examples=[100])] = 0
    xp_total: Annotated[int, Field(examples=[200])] = 0
    cool_points: Annotated[int, Field(examples=[100])] = 0


class User(BaseDocument):
    """Represent a user in the database and manage user-related data.

    Use this class to create, retrieve, update, and delete user records in the database. Store and manage user information such as ID, avatar, characters, campaign experience, creation date, macros, name, and associated guilds. Implement methods to handle user-specific operations and provide convenient access to user data.
    """

    name_first: Annotated[str | None, Field(min_length=3, max_length=50)] = None
    name_last: Annotated[str | None, Field(min_length=3, max_length=50)] = None
    username: Annotated[str, Field(min_length=3, max_length=50)]
    email: EmailStr
    role: UserRole = Field(default=UserRole.PLAYER)
    company_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])

    discord_profile: Annotated[DiscordProfile, Field(default_factory=DiscordProfile)]
    discord_oauth: Annotated[DiscordOauth, Field(default_factory=DiscordOauth)]

    campaign_experience: list[CampaignExperience] = Field(default_factory=list)

    asset_ids: list[PydanticObjectId] = Field(default_factory=list)

    def is_discord_oauth_expired(self) -> bool:
        """Check if the Discord OAuth token is expired."""
        from datetime import UTC, datetime

        if self.discord_oauth.expires_at is not None:
            return datetime.fromtimestamp(self.discord_oauth.expires_at, UTC) < datetime.now(UTC)

        return False

    async def get_or_create_campaign_experience(
        self, campaign_id: PydanticObjectId
    ) -> CampaignExperience:
        """Get the campaign experience for a campaign creating it if it doesn't exist.

        Args:
            campaign_id: The ID of the campaign to get the experience for.

        Returns:
            The campaign experience for the campaign.
        """
        campaign_experience = next(
            (
                experience
                for experience in self.campaign_experience
                if experience.campaign_id == campaign_id
            ),
            None,
        )

        if not campaign_experience:
            campaign_experience = CampaignExperience(campaign_id=campaign_id)
            self.campaign_experience.append(campaign_experience)
            await self.save()

        return campaign_experience

    async def update_campaign_experience(
        self, campaign_id: PydanticObjectId, updates: dict
    ) -> CampaignExperience:
        """Update campaign experience for a campaign.

        Args:
            campaign_id: The ID of the campaign.
            updates: Dictionary of fields to update.

        Returns:
            The updated campaign experience.
        """
        campaign_experience = await self.get_or_create_campaign_experience(campaign_id)

        for key, value in updates.items():
            setattr(campaign_experience, key, value)

        # Reassign to trigger change detection
        for i, exp in enumerate(self.campaign_experience):
            if exp.campaign_id == campaign_id:
                self.campaign_experience[i] = campaign_experience
                break

        await self.save()
        return campaign_experience

    async def has_xp(self, campaign_id: PydanticObjectId, amount: int) -> bool:
        """Check if the user has the required amount of XP.

        Args:
            campaign_id: The ID of the campaign.
            amount: The amount of XP required.

        Returns:
            True if the user has the required amount of XP, False otherwise.
        """
        campaign_experience = await self.get_or_create_campaign_experience(campaign_id)
        return campaign_experience.xp_current >= amount

    async def spend_xp(self, campaign_id: PydanticObjectId, amount: int) -> CampaignExperience:
        """Spend XP for a campaign.

        Args:
            campaign_id: The ID of the campaign.
            amount: The amount of XP to spend.
        """
        campaign_experience = await self.get_or_create_campaign_experience(campaign_id)
        if campaign_experience.xp_current < amount:
            raise NotEnoughXPError(current_xp=campaign_experience.xp_current, required_xp=amount)

        return await self.update_campaign_experience(
            campaign_id, {"xp_current": campaign_experience.xp_current - amount}
        )

    async def add_xp(
        self,
        campaign_id: PydanticObjectId,
        amount: int,
        *,
        update_total: bool = True,
    ) -> CampaignExperience:
        """Add XP to a campaign.

        Args:
            campaign_id: The ID of the campaign.
            amount: The amount of XP to add.
            update_total: Whether to update the total XP.

        Returns:
            The updated campaign experience.
        """
        campaign_experience = await self.get_or_create_campaign_experience(campaign_id)
        return await self.update_campaign_experience(
            campaign_id,
            {
                "xp_current": campaign_experience.xp_current + amount,
                "xp_total": campaign_experience.xp_total + amount
                if update_total
                else campaign_experience.xp_total,
            },
        )

    async def add_cp(self, campaign_id: PydanticObjectId, amount: int) -> CampaignExperience:
        """Add CP to a campaign.

        Args:
            campaign_id: The ID of the campaign.
            amount: The amount of CP to add.
        """
        campaign_experience = await self.get_or_create_campaign_experience(campaign_id)
        return await self.update_campaign_experience(
            campaign_id,
            {
                "cool_points": campaign_experience.cool_points + amount,
                "xp_current": campaign_experience.xp_current + (amount * COOL_POINT_VALUE),
                "xp_total": campaign_experience.xp_total + (amount * COOL_POINT_VALUE),
            },
        )

    class Settings:
        """Settings for the User model."""

        indexes: ClassVar[list[str]] = ["discord_profile.id", "user_role", "company_id"]
