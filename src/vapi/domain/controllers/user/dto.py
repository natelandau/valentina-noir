"""User DTOs."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import msgspec
from tortoise.exceptions import NoValuesFetched

from vapi.db.sql_models.quickroll import QuickRoll

if TYPE_CHECKING:
    from vapi.db.sql_models.user import CampaignExperience, User


# ---------------------------------------------------------------------------
# Response Structs
# ---------------------------------------------------------------------------


class CampaignExperienceResponse(msgspec.Struct):
    """Response body for campaign experience."""

    id: UUID
    campaign_id: UUID
    user_id: UUID
    xp_current: int
    xp_total: int
    cool_points: int

    @classmethod
    def from_model(cls, m: "CampaignExperience") -> "CampaignExperienceResponse":
        """Convert a Tortoise CampaignExperience to a response Struct."""
        return cls(
            id=m.id,
            campaign_id=m.campaign_id,  # type: ignore[attr-defined]
            user_id=m.user_id,  # type: ignore[attr-defined]
            xp_current=m.xp_current,
            xp_total=m.xp_total,
            cool_points=m.cool_points,
        )


class UserResponse(msgspec.Struct):
    """Response body for a user."""

    id: UUID
    date_created: datetime
    date_modified: datetime
    name_first: str | None
    name_last: str | None
    username: str
    email: str
    role: str
    company_id: UUID
    lifetime_xp: int
    lifetime_cool_points: int
    google_profile: dict | None
    github_profile: dict | None
    discord_profile: dict | None
    campaign_experience: list[CampaignExperienceResponse]

    @classmethod
    def from_model(cls, m: "User") -> "UserResponse":
        """Convert a Tortoise User to a response Struct.

        Requires ``campaign_experiences`` to be prefetched before calling.
        """
        try:
            experiences = [
                CampaignExperienceResponse.from_model(exp) for exp in m.campaign_experiences
            ]
        except (AttributeError, NoValuesFetched):
            experiences = []

        return cls(
            id=m.id,
            date_created=m.date_created,
            date_modified=m.date_modified,
            name_first=m.name_first,
            name_last=m.name_last,
            username=m.username,
            email=m.email,
            role=m.role.value,
            company_id=m.company_id,  # type: ignore[attr-defined]
            lifetime_xp=m.lifetime_xp,
            lifetime_cool_points=m.lifetime_cool_points,
            google_profile=m.google_profile,
            github_profile=m.github_profile,
            discord_profile=m.discord_profile,
            campaign_experience=experiences,
        )


# ---------------------------------------------------------------------------
# Request Structs
# ---------------------------------------------------------------------------


class UserCreate(msgspec.Struct):
    """Request body for creating a user."""

    username: str
    email: str
    role: str
    requesting_user_id: UUID
    name_first: str | None = None
    name_last: str | None = None
    discord_profile: dict | None = None
    google_profile: dict | None = None
    github_profile: dict | None = None


class UserPatch(msgspec.Struct):
    """Request body for partially updating a user.

    All fields use UNSET as default to distinguish 'not sent' from 'sent as null'.
    """

    requesting_user_id: UUID
    name_first: str | None | msgspec.UnsetType = msgspec.UNSET
    name_last: str | None | msgspec.UnsetType = msgspec.UNSET
    username: str | msgspec.UnsetType = msgspec.UNSET
    email: str | msgspec.UnsetType = msgspec.UNSET
    role: str | msgspec.UnsetType = msgspec.UNSET
    discord_profile: dict | None | msgspec.UnsetType = msgspec.UNSET
    google_profile: dict | None | msgspec.UnsetType = msgspec.UNSET
    github_profile: dict | None | msgspec.UnsetType = msgspec.UNSET


class UserApprove(msgspec.Struct):
    """Request body for approving an unapproved user."""

    role: str
    requesting_user_id: UUID


class UserDeny(msgspec.Struct):
    """Request body for denying an unapproved user."""

    requesting_user_id: UUID


class UserRegister(msgspec.Struct):
    """Request body for SSO registration (no requesting_user_id required)."""

    username: str
    email: str
    name_first: str | None = None
    name_last: str | None = None
    discord_profile: dict | None = None
    google_profile: dict | None = None
    github_profile: dict | None = None


class UserMerge(msgspec.Struct):
    """Request body for merging an UNAPPROVED user into a primary user."""

    primary_user_id: UUID
    secondary_user_id: UUID
    requesting_user_id: UUID


class ExperienceAddRemove(msgspec.Struct):
    """Request body for adding or removing XP/CP."""

    amount: int
    campaign_id: UUID
    requesting_user_id: UUID


# ---------------------------------------------------------------------------
# QuickRoll Structs (Tortoise)
# ---------------------------------------------------------------------------


class QuickRollCreate(msgspec.Struct):
    """Request body for creating a quick roll."""

    name: str
    description: str = ""
    trait_ids: list[UUID] = []


class QuickRollPatch(msgspec.Struct):
    """Request body for updating a quick roll."""

    name: str | msgspec.UnsetType = msgspec.UNSET
    description: str | msgspec.UnsetType = msgspec.UNSET
    trait_ids: list[UUID] | msgspec.UnsetType = msgspec.UNSET


class QuickRollResponse(msgspec.Struct):
    """Response body for a quick roll."""

    id: UUID
    date_created: datetime
    date_modified: datetime
    name: str
    description: str
    user_id: UUID
    trait_ids: list[UUID]

    @classmethod
    def from_model(cls, m: QuickRoll) -> "QuickRollResponse":
        """Convert a Tortoise QuickRoll to a response Struct."""
        return cls(
            id=m.id,
            date_created=m.date_created,
            date_modified=m.date_modified,
            name=m.name,
            description=m.description or "",
            user_id=m.user_id,  # type: ignore[attr-defined]
            trait_ids=[t.id for t in m.traits],
        )
