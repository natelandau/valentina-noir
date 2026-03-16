"""Services for controllers."""

from __future__ import annotations

from asyncio import gather
from typing import TYPE_CHECKING

from beanie.operators import In

from vapi.constants import CharacterClass, CharacterStatus
from vapi.db.models import (
    Character,
    CharacterTrait,
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)
from vapi.domain.controllers.character.dto import (
    CharacterFullSheetDTO,
    FullSheetCharacterTraitDTO,
    FullSheetTraitCategoryDTO,
    FullSheetTraitSectionDTO,
    FullSheetTraitSubcategoryDTO,
)
from vapi.lib.exceptions import ValidationError
from vapi.utils.time import time_now

from .character_trait_svc import CharacterTraitService
from .validation_svc import GetModelByIdValidationService

if TYPE_CHECKING:
    from vapi.db.models.character import NameDescriptionSubDocument
    from vapi.domain.controllers.character.dto import CharacterTraitCreate


class CharacterService:
    """Service class for Character business logic.

    Encapsulates validation and attribute management operations that can be called explicitly from controllers instead of relying on model hooks.
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
        """Assign vampire clan attributes to the character.

        Args:
            character: The character to assign attributes to.
        """
        if character.character_class != CharacterClass.VAMPIRE:
            return

        if not character.vampire_attributes or not character.vampire_attributes.clan_id:
            raise ValidationError(
                detail="Vampire clan id is required",
                invalid_parameters=[
                    {"field": "clan_id", "message": "Vampire clan id is required"},
                ],
            )

        clan = await GetModelByIdValidationService().get_vampire_clan_by_id(
            character.vampire_attributes.clan_id
        )

        updates: dict[str, str | NameDescriptionSubDocument | None] = {"clan_name": clan.name}

        if not character.vampire_attributes.bane or character.vampire_attributes.bane not in [
            clan.bane,
            clan.variant_bane,
        ]:
            updates["bane"] = clan.bane

        if (
            not character.vampire_attributes.compulsion
            or character.vampire_attributes.compulsion != clan.compulsion
        ):
            updates["compulsion"] = clan.compulsion

        character.vampire_attributes = character.vampire_attributes.model_copy(update=updates)

    async def assign_werewolf_attributes(self, character: Character) -> None:
        """Validate and populate werewolf attributes from tribe and auspice.

        Args:
            character: The character to validate.


        Raises:
            ValidationError: If tribe_id/auspice_id is missing or not found.
        """
        if character.character_class != CharacterClass.WEREWOLF:
            return

        if (
            not character.werewolf_attributes.tribe_id
            or not character.werewolf_attributes.auspice_id
        ):
            raise ValidationError(
                invalid_parameters=[
                    {"field": "tribe_id", "message": "Both tribe and auspice IDs are required"},
                    {"field": "auspice_id", "message": "Both tribe and auspice IDs are required"},
                ],
            )

        tribe = await GetModelByIdValidationService().get_werewolf_tribe_by_id(
            character.werewolf_attributes.tribe_id
        )

        auspice = await GetModelByIdValidationService().get_werewolf_auspice_by_id(
            character.werewolf_attributes.auspice_id
        )

        character.werewolf_attributes = character.werewolf_attributes.model_copy(
            update={"tribe_name": tribe.name, "auspice_name": auspice.name}
        )

    async def validate_unique_name(self, character: Character) -> None:
        """Validate that the character name is unique within the company.

        Args:
            character: The character to validate.

        Raises:
            ValidationError: If another character with the same name exists.
        """
        character_with_same_name = await Character.find(
            Character.name_first == character.name_first,
            Character.name_last == character.name_last,
            Character.is_archived == False,
            Character.id != character.id,
            Character.company_id == character.company_id,
        ).first_or_none()

        if character_with_same_name:
            msg = "Combination of name_first and name_last is not unique"
            raise ValidationError(
                invalid_parameters=[
                    {"field": "name_first", "message": msg},
                    {"field": "name_last", "message": msg},
                ],
            )

    async def apply_concept_specialties(self, character: Character) -> None:
        """Apply specialties from the character's concept.

        Args:
            character: The character to update.

        Returns:
            The updated list of specialties.

        Raises:
            ValidationError: If concept_id is set but concept not found.
        """
        if not character.concept_id:
            return

        concept = await GetModelByIdValidationService().get_concept_by_id(character.concept_id)

        if character.specialties != concept.specialties:
            character.specialties = concept.specialties

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

        Call this method before saving a character to ensure all validations pass and derived fields are properly set.

        Args:
            character: The character to prepare.
        """
        await self.validate_unique_name(character)
        self.update_date_killed(character)
        await self.validate_class_attributes(character)
        await self.apply_concept_specialties(character)

    async def character_create_trait_to_character_traits(
        self, character: Character, trait_create_data: list[CharacterTraitCreate]
    ) -> None:
        """Create traits for a character.

        Args:
            character: The character to create traits for.
            trait_create_data: The data for each trait to create.

        Raises:
            ValidationError: If a trait is not found.
        """
        for trait in trait_create_data:
            trait_obj = await GetModelByIdValidationService().get_trait_by_id(trait.trait_id)
            character_trait = await CharacterTrait(
                character_id=character.id,
                trait=trait_obj,
                value=trait.value,
            ).insert()

            character_trait_service = CharacterTraitService()
            await character_trait_service.after_save(character_trait)

    async def get_character_full_sheet(self, character: Character) -> CharacterFullSheetDTO:
        """Build the hierarchical full character sheet (sections > categories > subcategories > traits)."""
        all_character_traits = await CharacterTrait.find(
            CharacterTrait.character_id == character.id,
            fetch_links=True,
        ).to_list()

        sheet_section_ids: set = set()
        category_ids: set = set()
        subcategory_ids: set = set()

        # Pre-index traits by category and subcategory for O(1) lookups
        traits_by_subcategory: dict = {}
        traits_by_category_no_sub: dict = {}

        for ct in all_character_traits:
            trait: Trait = ct.trait  # type: ignore[assignment]
            sheet_section_ids.add(trait.sheet_section_id)
            category_ids.add(trait.parent_category_id)
            subcategory_ids.add(trait.trait_subcategory_id)

            if trait.trait_subcategory_id:
                traits_by_subcategory.setdefault(trait.trait_subcategory_id, []).append(ct)
            else:
                traits_by_category_no_sub.setdefault(trait.parent_category_id, []).append(ct)

        subcategory_ids.discard(None)

        sections_objects, categories_objects, subcategories_objects = await gather(
            CharSheetSection.find(
                CharSheetSection.is_archived == False,
                In(CharSheetSection.id, sheet_section_ids),
            )
            .sort("order")
            .to_list(),
            TraitCategory.find(
                TraitCategory.is_archived == False,
                In(TraitCategory.id, category_ids),
            )
            .sort("order")
            .to_list(),
            TraitSubcategory.find(
                TraitSubcategory.is_archived == False,
                In(TraitSubcategory.id, subcategory_ids),
            )
            .sort("name")
            .to_list(),
        )

        # Pre-index subcategories by parent category
        subcategories_by_category: dict = {}
        for subcategory in subcategories_objects:
            if subcategory.parent_category_id:
                subcategories_by_category.setdefault(subcategory.parent_category_id, []).append(
                    subcategory
                )

        # Pre-index categories by parent section
        categories_by_section: dict = {}
        for category in categories_objects:
            categories_by_section.setdefault(category.parent_sheet_section_id, []).append(category)

        def _build_trait_dto(ct: CharacterTrait) -> FullSheetCharacterTraitDTO:
            return FullSheetCharacterTraitDTO(trait=ct.trait, value=ct.value)  # type: ignore[arg-type]

        sections = [
            FullSheetTraitSectionDTO(
                name=section.name,
                description=section.description,
                order=section.order,
                show_when_empty=section.show_when_empty,
                categories=[
                    FullSheetTraitCategoryDTO(
                        name=category.name,
                        description=category.description,
                        order=category.order,
                        show_when_empty=category.show_when_empty,
                        initial_cost=category.initial_cost,
                        upgrade_cost=category.upgrade_cost,
                        subcategories=[
                            FullSheetTraitSubcategoryDTO(
                                name=sub.name,
                                description=sub.description,
                                show_when_empty=sub.show_when_empty,
                                initial_cost=sub.initial_cost,
                                upgrade_cost=sub.upgrade_cost,
                                requires_parent=sub.requires_parent,
                                pool=sub.pool,
                                system=sub.system,
                                hunter_edge_type=sub.hunter_edge_type,
                                character_traits=[
                                    _build_trait_dto(ct)
                                    for ct in traits_by_subcategory.get(sub.id, [])
                                ],
                            )
                            for sub in subcategories_by_category.get(category.id, [])
                        ],
                        character_traits=[
                            _build_trait_dto(ct)
                            for ct in traits_by_category_no_sub.get(category.id, [])
                        ],
                    )
                    for category in categories_by_section.get(section.id, [])
                ],
            )
            for section in sections_objects
        ]

        return CharacterFullSheetDTO(character=character, sections=sections)
