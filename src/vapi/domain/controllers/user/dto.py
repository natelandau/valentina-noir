"""User schemas."""

from typing import Annotated

from beanie import PydanticObjectId
from litestar.plugins.pydantic import PydanticDTO
from pydantic import BaseModel, EmailStr, Field

from vapi.constants import UserRole
from vapi.db.models import QuickRoll, User
from vapi.db.models.user import CampaignExperience, GitHubProfile, GoogleProfile
from vapi.lib.dto import dto_config


class DiscordProfileInput(BaseModel):
    """Discord profile input model that excludes the computed avatar_url field."""

    id: Annotated[str | None, Field(examples=["1234567890"])] = None
    username: Annotated[str | None, Field(examples=["John Doe"])] = None
    global_name: Annotated[str | None, Field(examples=["John Doe"])] = None
    avatar_id: Annotated[str | None, Field(examples=["1234567890"])] = None
    discriminator: Annotated[str | None, Field(examples=["1234"])] = None
    email: Annotated[str | None, Field(examples=["john.doe@example.com"])] = None
    verified: Annotated[bool | None, Field(examples=[True])] = None


class UserPostDTO(BaseModel):
    """User post/patch DTO."""

    name_first: Annotated[str | None, Field(examples=["John"])] = None
    name_last: Annotated[str | None, Field(examples=["Doe"])] = None
    username: Annotated[str, Field(examples=["john.doe"])]
    email: EmailStr = Field(examples=["john.doe@example.com"])
    role: UserRole = Field(examples=[UserRole.PLAYER])
    discord_profile: Annotated[DiscordProfileInput, Field(default_factory=DiscordProfileInput)]
    google_profile: Annotated[GoogleProfile, Field(default_factory=GoogleProfile)]
    github_profile: Annotated[GitHubProfile, Field(default_factory=GitHubProfile)]
    requesting_user_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])


class UserPatchDTO(BaseModel):
    """User post/patch DTO."""

    name_first: Annotated[str | None, Field(examples=["John"])] = None
    name_last: Annotated[str | None, Field(examples=["Doe"])] = None
    username: Annotated[str | None, Field(examples=["john.doe"])] = None
    email: Annotated[EmailStr | None, Field(examples=["john.doe@example.com"])] = None
    role: Annotated[UserRole | None, Field(examples=[UserRole.PLAYER])] = None
    discord_profile: Annotated[DiscordProfileInput | None, Field(default=None)]
    google_profile: Annotated[GoogleProfile | None, Field(default=None)]
    github_profile: Annotated[GitHubProfile | None, Field(default=None)]
    requesting_user_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])


class UserApproveDTO(BaseModel):
    """Approve an unapproved user and assign a role."""

    role: UserRole = Field(examples=[UserRole.PLAYER])
    requesting_user_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])


class UserDenyDTO(BaseModel):
    """Deny an unapproved user."""

    requesting_user_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])


class UserRegisterDTO(BaseModel):
    """Register a new user via SSO onboarding (no requesting_user_id required)."""

    name_first: Annotated[str | None, Field(examples=["John"])] = None
    name_last: Annotated[str | None, Field(examples=["Doe"])] = None
    username: Annotated[str, Field(examples=["john.doe"])]
    email: EmailStr = Field(examples=["john.doe@example.com"])
    discord_profile: Annotated[DiscordProfileInput, Field(default_factory=DiscordProfileInput)]
    google_profile: Annotated[GoogleProfile, Field(default_factory=GoogleProfile)]
    github_profile: Annotated[GitHubProfile, Field(default_factory=GitHubProfile)]


class UserMergeDTO(BaseModel):
    """Merge an UNAPPROVED user into an existing primary user."""

    primary_user_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])
    secondary_user_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])
    requesting_user_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])


class ReturnUserDTO(PydanticDTO[User]):
    """User DTO."""

    config = dto_config(exclude={"discord_oauth"})


class ReturnCampaignExperienceDTO(PydanticDTO[CampaignExperience]):
    """Campaign experience DTO."""

    config = dto_config()


class ExperienceAddRemove(BaseModel):
    """Experience and cool points add/remove model."""

    amount: Annotated[int, Field(examples=[100])]
    campaign_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])
    requesting_user_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])


class PostQuickRollDTO(PydanticDTO[QuickRoll]):
    """Quick roll create DTO."""

    config = dto_config(exclude={"id", "date_created", "date_modified", "user_id"})


class PatchQuickRollDTO(PydanticDTO[QuickRoll]):
    """Quick roll update DTO."""

    config = dto_config(partial=True, exclude={"id", "date_created", "date_modified", "user_id"})


class ReturnQuickRollDTO(PydanticDTO[QuickRoll]):
    """Quick roll DTO."""

    config = dto_config()
