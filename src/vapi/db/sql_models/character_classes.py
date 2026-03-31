"""Character class constant models: vampire clans, werewolf auspices and tribes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tortoise import fields

from vapi.constants import WerewolfRenown
from vapi.db.sql_models.base import BaseModel
from vapi.db.sql_models.validators import validate_game_versions

if TYPE_CHECKING:
    from vapi.db.sql_models.character import VampireAttributes, WerewolfAttributes
    from vapi.db.sql_models.character_sheet import Trait


class VampireClan(BaseModel):
    """A vampire clan with associated disciplines."""

    name = fields.CharField(max_length=50)
    description = fields.TextField(null=True)
    game_versions: Any = fields.JSONField(default=list, validators=[validate_game_versions])
    bane_name = fields.CharField(max_length=50, null=True)
    bane_description = fields.TextField(null=True)
    variant_bane_name = fields.CharField(max_length=50, null=True)
    variant_bane_description = fields.TextField(null=True)
    compulsion_name = fields.CharField(max_length=50, null=True)
    compulsion_description = fields.TextField(null=True)
    link = fields.TextField(null=True)

    # M2M
    disciplines: fields.ManyToManyRelation[Trait] = fields.ManyToManyField(
        "models.Trait", related_name="clans", through="vampire_clan_disciplines"
    )

    # Reverse relations
    characters: fields.ReverseRelation[VampireAttributes]

    class Meta:
        """Tortoise ORM meta options."""

        table = "vampire_clan"


class WerewolfAuspice(BaseModel):
    """A werewolf auspice with associated gifts."""

    name = fields.CharField(max_length=50)
    description = fields.TextField(null=True)
    game_versions: Any = fields.JSONField(default=list, validators=[validate_game_versions])
    link = fields.TextField(null=True)

    # M2M
    gifts: fields.ManyToManyRelation[Trait] = fields.ManyToManyField(
        "models.Trait", related_name="auspices", through="werewolf_auspice_gifts"
    )

    # Reverse relations
    characters: fields.ReverseRelation[WerewolfAttributes]

    class Meta:
        """Tortoise ORM meta options."""

        table = "werewolf_auspice"


class WerewolfTribe(BaseModel):
    """A werewolf tribe with associated gifts."""

    name = fields.CharField(max_length=50)
    description = fields.TextField(null=True)
    game_versions: Any = fields.JSONField(default=list, validators=[validate_game_versions])
    renown = fields.CharEnumField(WerewolfRenown)
    patron_spirit = fields.TextField(null=True)
    favor = fields.TextField(null=True)
    ban = fields.TextField(null=True)
    link = fields.TextField(null=True)

    # M2M
    gifts: fields.ManyToManyRelation[Trait] = fields.ManyToManyField(
        "models.Trait", related_name="tribes", through="werewolf_tribe_gifts"
    )

    # Reverse relations
    characters: fields.ReverseRelation[WerewolfAttributes]

    class Meta:
        """Tortoise ORM meta options."""

        table = "werewolf_tribe"
