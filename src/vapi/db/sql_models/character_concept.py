"""Character concept model."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tortoise import fields

from vapi.db.sql_models.base import BaseModel

if TYPE_CHECKING:
    from vapi.db.sql_models.character import Character
    from vapi.db.sql_models.company import Company


class CharacterConcept(BaseModel):
    """A pre-defined character archetype with favored abilities and specialties."""

    name = fields.CharField(max_length=50)
    description = fields.TextField()
    examples: Any = fields.JSONField(default=list)
    max_specialties = fields.IntField(default=0)
    specialties: Any = fields.JSONField(default=list)
    favored_ability_names: Any = fields.JSONField(default=list)

    company: fields.ForeignKeyRelation[Company] = fields.ForeignKeyField(
        "models.Company",
        related_name="character_concepts",
        on_delete=fields.OnDelete.CASCADE,
        null=True,
    )

    # Reverse relations
    characters: fields.ReverseRelation[Character]

    class Meta:
        """Tortoise ORM meta options."""

        table = "character_concept"
