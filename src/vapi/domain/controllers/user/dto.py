"""User schemas."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from litestar.plugins.pydantic import PydanticDTO
from pydantic import BaseModel, Field

from vapi.db.models import QuickRoll, User
from vapi.db.models.user import CampaignExperience
from vapi.lib.dto import dto_config


class PostUserDTO(PydanticDTO[User]):
    """User create DTO."""

    config = dto_config(
        exclude={
            "id",
            "date_created",
            "date_modified",
            "company_id",
            "campaign_experience",
            "discord_oauth",
        }
    )


class PatchUserDTO(PydanticDTO[User]):
    """User update DTO."""

    config = dto_config(
        partial=True,
        exclude={
            "id",
            "date_created",
            "date_modified",
            "company_id",
            "campaign_experience",
            "discord_oauth",
        },
    )


class ReturnUserDTO(PydanticDTO[User]):
    """User DTO."""

    config = dto_config(exclude={"discord_oauth"})


class ReturnCampaignExperienceDTO(PydanticDTO[CampaignExperience]):
    """Campaign experience DTO."""

    config = dto_config()


class ExperienceAddRemove(BaseModel):
    """Experience and cool points add/remove model."""

    amount: Annotated[int, Field(examples=[100])]
    user_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])
    campaign_id: PydanticObjectId = Field(examples=["68c1f7152cae3787a09a74fa"])


class PostQuickRollDTO(PydanticDTO[QuickRoll]):
    """Quick roll create DTO."""

    config = dto_config(exclude={"id", "date_created", "date_modified", "user_id"})


class PatchQuickRollDTO(PydanticDTO[QuickRoll]):
    """Quick roll update DTO."""

    config = dto_config(partial=True, exclude={"id", "date_created", "date_modified", "user_id"})


class ReturnQuickRollDTO(PydanticDTO[QuickRoll]):
    """Quick roll DTO."""

    config = dto_config()
