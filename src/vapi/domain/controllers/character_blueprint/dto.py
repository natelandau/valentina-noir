"""Character sheet DTOs."""

from __future__ import annotations

from litestar.plugins.pydantic import PydanticDTO

from vapi.db.models import (
    CharacterConcept,
    CharSheetSection,
    HunterEdge,
    HunterEdgePerk,
    Trait,
    TraitCategory,
    VampireClan,
    WerewolfAuspice,
    WerewolfGift,
    WerewolfRite,
    WerewolfTribe,
)
from vapi.lib.dto import dto_config


class CharacterSheetDTO(PydanticDTO[CharSheetSection]):
    """Character sheet DTO."""

    config = dto_config()


class TraitCategoryDTO(PydanticDTO[TraitCategory]):
    """Trait category DTO."""

    config = dto_config()


class TraitDTO(PydanticDTO[Trait]):
    """Trait DTO."""

    config = dto_config()


class ConceptDTO(PydanticDTO[CharacterConcept]):
    """Concept DTO."""

    config = dto_config(exclude={"company_id", "date_created", "date_modified"})


class VampireClanDTO(PydanticDTO[VampireClan]):
    """Vampire clan DTO."""

    config = dto_config()


class WerewolfTribeDTO(PydanticDTO[WerewolfTribe]):
    """Werewolf tribe DTO."""

    config = dto_config()


class WerewolfAuspiceDTO(PydanticDTO[WerewolfAuspice]):
    """Werewolf auspice DTO."""

    config = dto_config()


class WerewolfGiftDTO(PydanticDTO[WerewolfGift]):
    """Werewolf gift DTO."""

    config = dto_config()


class WerewolfRiteDTO(PydanticDTO[WerewolfRite]):
    """Werewolf rite DTO."""

    config = dto_config()


class HunterEdgeDTO(PydanticDTO[HunterEdge]):
    """Hunter edge DTO."""

    config = dto_config()


class HunterEdgePerkDTO(PydanticDTO[HunterEdgePerk]):
    """Hunter edge perk DTO."""

    config = dto_config()
