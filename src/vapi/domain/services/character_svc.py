"""Character business logic services."""

import asyncio
from typing import TYPE_CHECKING

from vapi.constants import CharacterClass, CharacterStatus
from vapi.db.sql_models.character import (
    Character,
    CharacterTrait,
    Specialty,
    VampireAttributes,
    WerewolfAttributes,
)
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import Trait
from vapi.lib.exceptions import ValidationError
from vapi.utils.time import time_now

if TYPE_CHECKING:
    from uuid import UUID

    from vapi.domain.controllers.character.dto import CharacterTraitCreate


class CharacterService:
    """Encapsulate validation and attribute management for characters.

    Called explicitly from controllers instead of relying on model hooks.
    """

    def update_date_killed(self, character: Character) -> None:
        """Update the death_date field based on character status.

        Args:
            character: The character to update.
        """
        if character.status == CharacterStatus.DEAD and character.date_killed is None:
            character.date_killed = time_now()
        elif character.status == CharacterStatus.ALIVE and character.date_killed is not None:
            character.date_killed = None

    async def assign_vampire_clan_attributes(self, character: Character) -> None:
        """Validate and populate vampire clan attributes from the clan FK.

        Args:
            character: The character to assign attributes to.
        """
        if character.character_class != CharacterClass.VAMPIRE:
            return

        # During create, vampire_attributes may not exist yet as a DB row.
        # The controller passes clan_id; we need to look it up.
        vampire_attrs = await VampireAttributes.filter(character=character).first()
        clan_id: UUID | None = vampire_attrs.clan_id if vampire_attrs else None  # type: ignore[attr-defined]

        if not clan_id:
            raise ValidationError(
                detail="Vampire clan id is required",
                invalid_parameters=[
                    {"field": "clan_id", "message": "Vampire clan id is required"},
                ],
            )

        clan = await VampireClan.filter(id=clan_id, is_archived=False).first()
        if not clan:
            raise ValidationError(detail=f"Vampire clan {clan_id} not found")

        updates: dict[str, object] = {"clan": clan}

        if not vampire_attrs.bane_name or vampire_attrs.bane_name not in [
            clan.bane_name,
            clan.variant_bane_name,
        ]:
            updates["bane_name"] = clan.bane_name
            updates["bane_description"] = clan.bane_description

        if (
            not vampire_attrs.compulsion_name
            or vampire_attrs.compulsion_name != clan.compulsion_name
        ):
            updates["compulsion_name"] = clan.compulsion_name
            updates["compulsion_description"] = clan.compulsion_description

        for key, value in updates.items():
            setattr(vampire_attrs, key, value)
        await vampire_attrs.save()

    async def assign_werewolf_attributes(self, character: Character) -> None:
        """Validate and populate werewolf attributes from tribe and auspice FKs.

        Args:
            character: The character to validate.

        Raises:
            ValidationError: If tribe_id/auspice_id is missing or not found.
        """
        if character.character_class != CharacterClass.WEREWOLF:
            return

        werewolf_attrs = await WerewolfAttributes.filter(character=character).first()
        tribe_id: UUID | None = werewolf_attrs.tribe_id if werewolf_attrs else None  # type: ignore[attr-defined]
        auspice_id: UUID | None = werewolf_attrs.auspice_id if werewolf_attrs else None  # type: ignore[attr-defined]

        if not tribe_id or not auspice_id:
            raise ValidationError(
                invalid_parameters=[
                    {"field": "tribe_id", "message": "Both tribe and auspice IDs are required"},
                    {"field": "auspice_id", "message": "Both tribe and auspice IDs are required"},
                ],
            )

        tribe, auspice = await asyncio.gather(
            WerewolfTribe.filter(id=tribe_id, is_archived=False).first(),
            WerewolfAuspice.filter(id=auspice_id, is_archived=False).first(),
        )

        if not tribe:
            raise ValidationError(detail=f"Werewolf tribe {tribe_id} not found")
        if not auspice:
            raise ValidationError(detail=f"Werewolf auspice {auspice_id} not found")

        werewolf_attrs.tribe = tribe
        werewolf_attrs.auspice = auspice
        await werewolf_attrs.save()

    async def validate_unique_name(self, character: Character) -> None:
        """Validate that the character name is unique within the company.

        Args:
            character: The character to validate.

        Raises:
            ValidationError: If another character with the same name exists.
        """
        qs = Character.filter(
            name_first=character.name_first,
            name_last=character.name_last,
            is_archived=False,
            company_id=character.company_id,  # type: ignore[attr-defined]
        ).exclude(id=character.id)

        if await qs.first():
            msg = "Combination of name_first and name_last is not unique"
            raise ValidationError(
                invalid_parameters=[
                    {"field": "name_first", "message": msg},
                    {"field": "name_last", "message": msg},
                ],
            )

    async def apply_concept_specialties(self, character: Character) -> None:
        """Sync specialties from the character's concept to the Specialty table.

        Args:
            character: The character to update.

        Raises:
            ValidationError: If concept_id is set but concept not found.
        """
        concept_id: UUID | None = character.concept_id  # type: ignore[attr-defined]
        if not concept_id:
            return

        concept = await CharacterConcept.filter(id=concept_id, is_archived=False).first()
        if not concept:
            raise ValidationError(detail=f"Concept {concept_id} not found")

        # concept.specialties is a JSONField list of dicts: [{"name": ..., "type": ..., "description": ...}]
        desired = {(s["name"], s["type"]) for s in concept.specialties}
        existing = await Specialty.filter(character=character)
        existing_keys = {
            (s.name, s.type.value if hasattr(s.type, "value") else s.type) for s in existing
        }

        # Bulk-delete specialties no longer in the concept
        stale_ids = [
            spec.id
            for spec in existing
            if (spec.name, spec.type.value if hasattr(spec.type, "value") else spec.type)
            not in desired
        ]
        if stale_ids:
            await Specialty.filter(id__in=stale_ids).delete()

        # Bulk-create specialties that are new
        new_specialties = [
            Specialty(
                character=character,
                name=s["name"],
                type=s["type"],
                description=s.get("description", ""),
            )
            for s in concept.specialties
            if (s["name"], s["type"]) not in existing_keys
        ]
        if new_specialties:
            await Specialty.bulk_create(new_specialties)

    async def validate_class_attributes(self, character: Character) -> None:
        """Validate class-specific attributes (vampire, werewolf, etc.).

        Args:
            character: The character to validate.
        """
        match character.character_class:
            case CharacterClass.VAMPIRE:
                await self.assign_vampire_clan_attributes(character)
            case CharacterClass.WEREWOLF:
                await self.assign_werewolf_attributes(character)
            case _:
                pass

    async def prepare_for_save(self, character: Character) -> None:
        """Perform all pre-save validations and updates.

        Call before saving a character to ensure all validations pass and derived
        fields are properly set.

        Args:
            character: The character to prepare.
        """
        self.update_date_killed(character)
        await asyncio.gather(
            self.validate_unique_name(character),
            self.validate_class_attributes(character),
            self.apply_concept_specialties(character),
        )

    async def character_create_trait_to_character_traits(
        self, character: Character, trait_create_data: list["CharacterTraitCreate"]
    ) -> None:
        """Create CharacterTrait rows for a newly created character.

        The after_save derived-trait sync (willpower, total_renown) is deferred to
        Session 8.5 when CharacterTraitService migrates.

        Args:
            character: The character to create traits for.
            trait_create_data: The data for each trait to create.

        Raises:
            ValidationError: If a trait is not found.
        """
        trait_ids = [t.trait_id for t in trait_create_data]
        all_traits = await Trait.filter(id__in=trait_ids)
        trait_lookup: dict[UUID, Trait] = {t.id: t for t in all_traits}

        rows: list[CharacterTrait] = []
        for trait_data in trait_create_data:
            trait_obj = trait_lookup.get(trait_data.trait_id)
            if trait_obj is None:
                raise ValidationError(detail=f"Trait {trait_data.trait_id} not found")

            rows.append(
                CharacterTrait(
                    character=character,
                    trait=trait_obj,
                    value=trait_data.value,
                )
            )

        if rows:
            await CharacterTrait.bulk_create(rows)

    async def archive_character(self, character: Character) -> None:
        """Soft-delete a character.

        Cascade wiring for child entities (inventory, traits, assets, notes) will be
        added as each domain migrates in later sessions.

        Args:
            character: The character to archive.
        """
        character.is_archived = True
        character.archive_date = time_now()
        await character.save()
