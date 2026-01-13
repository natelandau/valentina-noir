"""Models for the character classes such as vampire clans, werewolf tribes, and werewolf auspices that are specific to a character class."""

from __future__ import annotations

from typing import Annotated

from beanie import PydanticObjectId  # noqa: TC002
from pydantic import Field

from vapi.constants import GameVersion, HunterEdgeType, WerewolfRenown
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

    gift_ids: list[PydanticObjectId] = Field(default_factory=list)
    link: str | None = None


class WerewolfTribe(CharacterClassConstant):
    """Werewolf tribe model."""

    renown: WerewolfRenown
    patron_spirit: str | None = None
    favor: str | None = None
    ban: str | None = None
    gift_ids: list[PydanticObjectId] = Field(default_factory=list)
    link: str | None = None


class WerewolfGift(CharacterClassConstant):
    """Werewolf gift model."""

    renown: WerewolfRenown
    cost: str | None = None
    duration: str | None = None
    dice_pool: list[str] = Field(default_factory=list)
    opposing_pool: list[str] = Field(default_factory=list)
    minimum_renown: int | None = None
    is_native_gift: bool = False
    notes: str | None = None
    tribe_id: PydanticObjectId | None = Field(default=None, examples=["68c1f7152cae3787a09a74fa"])
    auspice_id: PydanticObjectId | None = Field(default=None, examples=["68c1f7152cae3787a09a74fa"])


class WerewolfRite(CharacterClassConstant):
    """Werewolf rite model."""

    pool: str | None = None


class HunterEdge(CharacterClassConstant):
    """Hunter edge model."""

    pool: str | None = None
    system: str | None = None
    type: HunterEdgeType | None = None
    perk_ids: list[PydanticObjectId] = Field(default_factory=list)


class HunterEdgePerk(CharacterClassConstant):
    """Hunter edge perk model."""

    edge_id: PydanticObjectId | None = Field(default=None, examples=["68c1f7152cae3787a09a74fa"])
