"""Models for the character classes such as vampire clans, werewolf tribes, and werewolf auspices that are specific to a character class."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from pydantic import Field

from vapi.constants import GameVersion, WerewolfRenown
from vapi.db.models.base import BaseDocument, NameDescriptionSubDocument


class CharacterClassConstant(BaseDocument):
    """Base class details model."""

    name: str
    description: str | None = None
    game_versions: Annotated[
        list[GameVersion], Field(default_factory=lambda: [GameVersion.V4, GameVersion.V5])
    ]

    class Settings:
        """Settings for the CharacterClassConstant model."""

        is_root = True


class VampireClan(CharacterClassConstant):
    """Vampire clan model."""

    discipline_ids: list[PydanticObjectId] = Field(default_factory=list)
    bane: Annotated[NameDescriptionSubDocument | None, Field(default=None)] = None
    variant_bane: Annotated[NameDescriptionSubDocument | None, Field(default=None)] = None
    compulsion: Annotated[NameDescriptionSubDocument | None, Field(default=None)] = None
    link: str | None = None


class WerewolfAuspice(CharacterClassConstant):
    """Werewolf auspice model."""

    gift_trait_ids: list[PydanticObjectId] = Field(default_factory=list)
    link: str | None = None


class WerewolfTribe(CharacterClassConstant):
    """Werewolf tribe model."""

    renown: WerewolfRenown
    patron_spirit: str | None = None
    favor: str | None = None
    ban: str | None = None
    gift_trait_ids: list[PydanticObjectId] = Field(default_factory=list)
    link: str | None = None
