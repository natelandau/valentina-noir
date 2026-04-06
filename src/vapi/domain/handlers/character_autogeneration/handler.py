"""RNG character generation library."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from numpy import int32
from numpy.random import default_rng
from tortoise.expressions import Q
from tortoise.transactions import in_transaction

from vapi.constants import CharacterClass, CharacterType, GameVersion, HunterCreed
from vapi.db.sql_models.character import (
    Character,
    CharacterTrait,
    HunterAttributes,
    VampireAttributes,
    WerewolfAttributes,
)
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import (
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)
from vapi.domain.services import CharacterTraitService

from .constants import (
    ABILITY_DOT_BONUS,
    ABILITY_FOCUS_DOT_DISTRIBUTION,
    ADVANTAGE_STARTING_DOTS,
    ATTRIBUTE_DOT_BONUS,
    ATTRIBUTE_DOT_DISTRIBUTION,
    EXTRA_DISCIPLINES_MAP,
    EXTRA_HUNTER_EDGE_MAP,
    EXTRA_HUNTER_EDGE_PERK_MAP,
    EXTRA_WEREWOLF_GIFT_MAP,
    FLAW_STARTING_DOTS,
    NUM_WEREWOLF_RITE_MAP,
    WEREWOLF_RENOWN_BONUS,
    AbilityFocus,
    AutoGenExperienceLevel,
)
from .utils import (
    adjust_trait_value_based_on_level,
    divide_total_randomly,
    generate_unique_name,
    get_character_class_from_percentile,
    shuffle_and_adjust_trait_values,
)

if TYPE_CHECKING:
    from uuid import UUID

    from vapi.db.sql_models.campaign import Campaign
    from vapi.db.sql_models.company import Company
    from vapi.db.sql_models.user import User

_rng = default_rng()

logger = logging.getLogger("vapi")


class CharacterAutogenerationHandler:
    """Randomly generate different parts of a character.

    This class provides methods to randomly generate various aspects of a character, including attributes, abilities, and other traits based on the specified experience level and campaign settings.

    Args:
        user (User): The user for whom the character is being generated.
        experience_level (AutoGenExperienceLevel, optional): The experience level for character generation.
            Defaults to a random level if not specified.
        campaign (Campaign, optional): The campaign associated with the character.
            Defaults to None.

    Attributes:
        ctx (ValentinaContext): The context of the Discord application.
        user (User): The user for whom the character is being generated.
        experience_level (AutoGenExperienceLevel): The experience level for character generation.
        campaign (Campaign): The campaign associated with the character, if any.
    """

    def __init__(
        self,
        user: User,
        company: Company,
        campaign: Campaign,
    ) -> None:
        self.company = company
        self.user = user
        self.experience_level: AutoGenExperienceLevel | None = None
        self.campaign = campaign
        self.skill_focus: AbilityFocus | None = None
        self.concept: CharacterConcept | None = None
        self.character_trait_service = CharacterTraitService()

    async def generate_character(  # noqa: PLR0913
        self,
        character_type: CharacterType,
        experience_level: AutoGenExperienceLevel | None = None,
        skill_focus: AbilityFocus | None = None,
        char_class: CharacterClass | None = None,
        concept: CharacterConcept | None = None,
        vampire_clan: VampireClan | None = None,
        werewolf_tribe: WerewolfTribe | None = None,
        werewolf_auspice: WerewolfAuspice | None = None,
    ) -> Character:
        """Generate a base character with random attributes.

        Generate a base character with randomly selected attributes including class, concept, clan (for vampires), creed (for hunters), and name. Traits and customizations are not included in this base generation.

        Args:
            character_type: The type of character to generate.
            char_class: The character class to generate. If None, a random class will be selected.
            skill_focus: The skill focus to generate. If None, a random skill focus will be selected.
            experience_level: The experience level to generate. If None, a random experience level will be selected.
            concept: The concept to generate. If None, a random concept will be selected.
            vampire_clan: The vampire clan to generate. If None, a random clan will be selected if the class is vampire or ghoul.
            werewolf_tribe: The werewolf tribe to generate. If None, a random tribe will be selected if the class is werewolf.
            werewolf_auspice: The werewolf auspice to generate. If None, a random auspice will be selected if the class is werewolf.

        Returns:
            Character: The generated base character.
        """
        async with in_transaction():
            character = await self._generate_base_character(
                character_type, experience_level, skill_focus, char_class, concept
            )

            match character.character_class:
                case CharacterClass.VAMPIRE:
                    await self._generate_vampire_attributes(character, vampire_clan)
                case CharacterClass.WEREWOLF:
                    await self._generate_werewolf_attributes(
                        character, werewolf_tribe, werewolf_auspice
                    )
                    await self._generate_werewolf_gifts_and_rites(character)
                case CharacterClass.HUNTER:
                    await self._generate_hunter_attributes(character)

            await self._generate_attribute_values(character)
            await self._generate_ability_values(character)
            await self._generate_willpower_value(character)
            await self._generate_merit_background_values(character)
            await self._generate_flaw_values(character)
            await self._generate_humanity_value(character)

            await character.refresh_from_db()
            return character

    async def _generate_base_character(
        self,
        character_type: CharacterType,
        experience_level: AutoGenExperienceLevel | None = None,
        skill_focus: AbilityFocus | None = None,
        char_class: CharacterClass | None = None,
        concept: CharacterConcept | None = None,
        game_version: GameVersion = GameVersion.V5,
    ) -> Character:
        """Generate a base character with random attributes.

        Args:
            character_type: The type of character to generate.
            experience_level: The experience level to generate. If None, a random experience level will be selected.
            skill_focus: The skill focus to generate. If None, a random skill focus will be selected.
            char_class: The character class to generate. If None, a random class will be selected.
            concept: The concept to generate. If None, a random concept will be selected.
            game_version: The game version to generate. If None, V5 will be selected.

        Returns:
            Character: The generated base character.
        """
        self.skill_focus = skill_focus or random.choice(list[AbilityFocus](AbilityFocus))
        self.experience_level = experience_level or AutoGenExperienceLevel.NEW

        name_first, name_last = await generate_unique_name(self.company.id)

        if char_class is None:
            char_class = get_character_class_from_percentile()

        if concept is None:
            concepts = await CharacterConcept.filter(
                Q(company_id=self.company.id) | Q(company_id__isnull=True),
                is_archived=False,
            )
            concept = random.choice(list(concepts))

        self.concept = concept

        return await Character.create(
            is_chargen=True,
            name_first=name_first,
            name_last=name_last,
            character_class=char_class,
            concept=concept,
            company=self.company,
            campaign=self.campaign,
            type=character_type,
            game_version=game_version,
            user_creator=self.user,
            user_player=self.user,
        )

    async def _generate_attribute_values(self, character: Character) -> None:
        """Randomly generate attributes for the character.

        Generate and assign random attribute values for the given character based on their concept, class, and experience level. This method handles the distribution of attribute dots across physical, social, and mental categories.

        Args:
            character (Character): The character for which to generate attributes.
        """
        dots_to_apply = shuffle_and_adjust_trait_values(
            trait_values=ATTRIBUTE_DOT_DISTRIBUTION,
            experience_level=self.experience_level,
            dot_bonus=ATTRIBUTE_DOT_BONUS,
        )

        attribute_section = await CharSheetSection.filter(name="Attributes").first()
        categories = list(
            await TraitCategory.filter(
                sheet_section_id=attribute_section.id,
                character_classes__contains=[character.character_class],
                game_versions__contains=[character.game_version],
                is_archived=False,
            )
        )
        shuffled_categories = random.sample(categories, len(categories))

        for category in shuffled_categories:
            category_traits = await Trait.filter(
                category_id=category.id,
                character_classes__contains=[character.character_class],
                game_versions__contains=[character.game_version],
                is_archived=False,
                custom_for_character_id__isnull=True,
            )

            for t in category_traits:
                character_trait = await CharacterTrait.create(
                    value=dots_to_apply.pop(0),
                    character=character,
                    trait=t,
                )
                await self.character_trait_service.after_save(character_trait, character)

    async def _generate_willpower_value(self, character: Character) -> None:
        """Randomly generate willpower value for the character.

        Generate and assign random willpower value for the given character based on their concept, class, and experience level.

        Args:
            character (Character): The character for which to generate willpower value.
        """
        if character.game_version != GameVersion.V4:
            return

        willpower_trait = await Trait.filter(name="Willpower").first()
        await CharacterTrait.create(
            value=random.randint(3, 7),
            character=character,
            trait=willpower_trait,
        )

    async def _generate_humanity_value(self, character: Character) -> None:
        """Randomly generate humanity value for the character.

        Generate and assign random humanity value for the given character based on their concept, class, and experience level.

        Args:
            character (Character): The character for which to generate humanity value.
        """
        humanity_trait = await Trait.filter(name="Humanity").first()
        if character.character_class not in humanity_trait.character_classes:
            return

        character_trait = await CharacterTrait.create(
            value=7,
            character=character,
            trait=humanity_trait,
        )
        await self.character_trait_service.after_save(character_trait, character)

    async def _generate_ability_values(self, character: Character) -> None:
        """Randomly generate ability values for the character.

        Generate and assign random ability values for the given character based on their concept, class, and experience level.

        Args:
            character (Character): The character for which to generate abilities.
        """
        dots_to_apply = shuffle_and_adjust_trait_values(
            ABILITY_FOCUS_DOT_DISTRIBUTION[self.skill_focus],
            self.experience_level,
            ABILITY_DOT_BONUS,
        )

        ability_section = await CharSheetSection.filter(name="Abilities").first()
        categories = list(
            await TraitCategory.filter(
                sheet_section_id=ability_section.id,
                character_classes__contains=[character.character_class],
                game_versions__contains=[character.game_version],
                is_archived=False,
            )
        )

        abilities = list(
            await Trait.filter(
                category_id__in=[x.id for x in categories],
                character_classes__contains=[character.character_class],
                game_versions__contains=[character.game_version],
                is_archived=False,
                custom_for_character_id__isnull=True,
            )
        )
        shuffled_abilities = random.sample(abilities, len(abilities))

        abilities_by_name = {a.name: a for a in shuffled_abilities}
        for ability_name in self.concept.favored_ability_names:
            trait = abilities_by_name.get(ability_name)
            if not trait:
                continue

            shuffled_abilities.remove(trait)
            if dots_to_apply:
                value = max(dots_to_apply)
                dots_to_apply.remove(value)

            else:
                value = trait.min_value
            character_trait = await CharacterTrait.create(
                value=value,
                character=character,
                trait=trait,
            )
            await self.character_trait_service.after_save(character_trait, character)

        for ability in shuffled_abilities:
            value = dots_to_apply.pop(0) if dots_to_apply else ability.min_value
            character_trait = await CharacterTrait.create(
                value=value,
                character=character,
                trait=ability,
            )
            await self.character_trait_service.after_save(character_trait, character)

    async def _generate_vampire_attributes(
        self, character: Character, vampire_clan: VampireClan | None = None
    ) -> None:
        """Randomly generate vampire attributes for the character.

        Generate and assign random vampire attributes for the given character based on their concept, class, and experience level.

        Args:
            character (Character): The character for which to generate vampire attributes.
            vampire_clan (VampireClan | None): The vampire clan to generate. If None, a random clan will be selected.
        """
        if character.character_class not in {CharacterClass.VAMPIRE, CharacterClass.GHOUL}:
            return

        if not vampire_clan:
            vampire_clan = random.choice(list(await VampireClan.filter(is_archived=False)))

        if character.character_class == CharacterClass.VAMPIRE:
            # Pick between the standard bane and the variant bane when both exist
            if vampire_clan.bane_name and vampire_clan.variant_bane_name:
                chosen_bane_name, chosen_bane_desc = random.choice(
                    [
                        (vampire_clan.bane_name, vampire_clan.bane_description),
                        (vampire_clan.variant_bane_name, vampire_clan.variant_bane_description),
                    ]
                )
            else:
                chosen_bane_name = vampire_clan.bane_name
                chosen_bane_desc = vampire_clan.bane_description

            await VampireAttributes.create(
                character=character,
                clan=vampire_clan,
                bane_name=chosen_bane_name,
                bane_description=chosen_bane_desc,
                compulsion_name=vampire_clan.compulsion_name,
                compulsion_description=vampire_clan.compulsion_description,
            )

        await vampire_clan.fetch_related("disciplines")
        disciplines_to_set = list(vampire_clan.disciplines)

        disciplines_category = await TraitCategory.filter(name="Disciplines").first()
        all_disciplines = list(
            await Trait.filter(
                category_id=disciplines_category.id,
                character_classes__contains=[character.character_class],
                game_versions__contains=[character.game_version],
                is_archived=False,
                custom_for_character_id__isnull=True,
            )
        )

        disciplines_to_set.extend(
            random.sample(
                [x for x in all_disciplines if x not in disciplines_to_set],
                EXTRA_DISCIPLINES_MAP.get(self.experience_level, 0),
            ),
        )

        distributions = {
            AutoGenExperienceLevel.NEW: (1.0, 2.0),
            AutoGenExperienceLevel.INTERMEDIATE: (1.5, 2.0),
            AutoGenExperienceLevel.ADVANCED: (2.5, 2.0),
            AutoGenExperienceLevel.ELITE: (3.0, 2.0),
        }

        mean, distribution = distributions[self.experience_level]
        values = [
            adjust_trait_value_based_on_level(self.experience_level, x)
            for x in _rng.normal(mean, distribution, len(disciplines_to_set)).astype(int32)
        ]
        for discipline, value in zip(disciplines_to_set, values, strict=True):
            character_trait = await CharacterTrait.create(
                value=value,
                character=character,
                trait=discipline,
            )
            await self.character_trait_service.after_save(character_trait, character)

    async def _generate_werewolf_attributes(
        self,
        character: Character,
        werewolf_tribe: WerewolfTribe | None = None,
        werewolf_auspice: WerewolfAuspice | None = None,
    ) -> None:
        """Randomly generate werewolf attributes for the character.

        Generate and assign random werewolf attributes for the given character based on their concept, class, and experience level.

        Args:
            character (Character): The character for which to generate werewolf attributes.
            werewolf_tribe (WerewolfTribe | None): The werewolf tribe to generate. If None, a random tribe will be selected.
            werewolf_auspice (WerewolfAuspice | None): The werewolf auspice to generate. If None, a random auspice will be selected.
        """
        if character.character_class != CharacterClass.WEREWOLF:
            return

        if not werewolf_tribe:
            werewolf_tribe = random.choice(list(await WerewolfTribe.filter(is_archived=False)))
        if not werewolf_auspice:
            werewolf_auspice = random.choice(list(await WerewolfAuspice.filter(is_archived=False)))

        await WerewolfAttributes.create(
            character=character,
            tribe=werewolf_tribe,
            auspice=werewolf_auspice,
        )

        rage_and_renown = await Trait.filter(
            name__in=["Rage", "Honor", "Wisdom", "Glory"],
        )
        traits_by_name = {t.name: t for t in rage_and_renown}

        rage_trait = traits_by_name.get("Rage")
        if rage_trait:
            character_trait = await CharacterTrait.create(
                value=random.randint(1, 3),
                character=character,
                trait=rage_trait,
            )
            await self.character_trait_service.after_save(character_trait, character)

        renown_traits = [traits_by_name[n] for n in ("Honor", "Wisdom", "Glory")]
        tribe_renown_trait = next(
            x for x in renown_traits if x.name.lower() == werewolf_tribe.renown.name.lower()
        )
        not_tribe_renown_traits = [
            x for x in renown_traits if x.name.lower() != werewolf_tribe.renown.name.lower()
        ]
        shuffled_not_tribe_renown_traits = random.sample(
            not_tribe_renown_traits, len(not_tribe_renown_traits)
        )

        character_trait = await CharacterTrait.create(
            value=2 + WEREWOLF_RENOWN_BONUS[self.experience_level],
            character=character,
            trait=tribe_renown_trait,
        )
        await self.character_trait_service.after_save(character_trait, character)

        for i, trait in enumerate(shuffled_not_tribe_renown_traits):
            character_trait = await CharacterTrait.create(
                value=i + WEREWOLF_RENOWN_BONUS[self.experience_level],
                character=character,
                trait=trait,
            )
            await self.character_trait_service.after_save(character_trait, character)

    async def _generate_hunter_attributes(self, character: Character) -> None:
        """Randomly generate hunter attributes for the character.

        Generate and assign random hunter attributes for the given character based on their concept, class, and experience level.
        """
        if character.character_class != CharacterClass.HUNTER:
            return

        # New characters select between 2 Edges and 1 Perk or 1 Edge and 2 Perks.
        starting_num_edges = random.choice([2, 1])
        starting_num_perks = 1 if starting_num_edges == 2 else 2  # noqa: PLR2004

        num_edges = starting_num_edges + EXTRA_HUNTER_EDGE_MAP[self.experience_level]
        num_perks = starting_num_perks + EXTRA_HUNTER_EDGE_PERK_MAP[self.experience_level]

        edges_trait_category = await TraitCategory.filter(name="Edges").first()
        all_edges = list(
            await TraitSubcategory.filter(
                category_id=edges_trait_category.id,
                is_archived=False,
            )
        )

        selected_edges = random.sample(all_edges, num_edges)

        possible_perks = list(
            await Trait.filter(
                subcategory_id__in=[x.id for x in selected_edges],
                is_archived=False,
            )
        )

        selected_perks = random.sample(possible_perks, num_perks)
        for perk in selected_perks:
            character_trait = await CharacterTrait.create(
                value=1,
                character=character,
                trait=perk,
            )
            await self.character_trait_service.after_save(character_trait, character)

        creed = random.choice(list(HunterCreed))
        await HunterAttributes.create(
            character=character,
            creed=creed.value.title(),
        )

    async def _generate_werewolf_gifts_and_rites(self, character: Character) -> None:
        """Randomly generate werewolf gifts and rites for the character.

        Generate and assign random werewolf gifts and rites for the given character based on their concept, class, and experience level. Creates CharacterTrait rows instead of modifying werewolf_attributes directly.

        Args:
            character (Character): The character for which to generate werewolf gifts.
        """
        if character.character_class != CharacterClass.WEREWOLF:
            return

        werewolf_attrs = await WerewolfAttributes.filter(character=character).first()
        total_renown = werewolf_attrs.total_renown
        auspice_id = werewolf_attrs.auspice_id  # type: ignore[attr-defined]
        tribe_id = werewolf_attrs.tribe_id  # type: ignore[attr-defined]

        (
            tribe_gifts,
            auspice_gifts,
            native_gifts,
            rites_category,
            existing_char_traits,
        ) = await asyncio.gather(
            Trait.filter(
                gift_tribe_id__isnull=False,
                gift_tribe_id=tribe_id,
                gift_minimum_renown__lte=total_renown,
            ).all(),
            Trait.filter(
                gift_auspice_id__isnull=False,
                gift_auspice_id=auspice_id,
                gift_minimum_renown__lte=total_renown,
            ).all(),
            Trait.filter(
                gift_is_native=True,
                gift_minimum_renown__lte=total_renown,
            ).all(),
            TraitCategory.filter(name="Rites").first(),
            CharacterTrait.filter(character=character).prefetch_related("trait").all(),
        )

        rites = list(await Trait.filter(category_id=rites_category.id)) if rites_category else []
        existing_trait_ids: set[UUID] = {ct.trait.id for ct in existing_char_traits}

        value_modifiers = divide_total_randomly(
            total=EXTRA_WEREWOLF_GIFT_MAP[self.experience_level], num=3, max_value=5
        )

        async def _assign_random_traits(pool: list[Trait], count: int) -> None:
            available = [t for t in pool if t.id not in existing_trait_ids]
            chosen = random.sample(available, min(count, len(available)))
            for trait in chosen:
                await CharacterTrait.create(character=character, trait=trait, value=1)
                existing_trait_ids.add(trait.id)

        await _assign_random_traits(tribe_gifts, 1 + value_modifiers[0])
        await _assign_random_traits(auspice_gifts, 1 + value_modifiers[1])
        await _assign_random_traits(native_gifts, 1 + value_modifiers[2])
        await _assign_random_traits(rites, NUM_WEREWOLF_RITE_MAP[self.experience_level])

    async def _distribute_dots_across_traits(
        self,
        character: Character,
        possible_traits: list[Trait],
        num_dots: int,
    ) -> None:
        """Randomly distribute dots across traits and persist them.

        Args:
            character: The character to assign traits to.
            possible_traits: Pool of traits to choose from.
            num_dots: Total dots to distribute.
        """
        traits_by_id: dict[UUID, Trait] = {t.id: t for t in possible_traits}
        dot_assignments: dict[UUID, int] = {}

        while num_dots > 0:
            trait = random.choice(possible_traits)

            if trait.id in dot_assignments:
                if dot_assignments[trait.id] < trait.max_value:
                    dot_assignments[trait.id] += 1
                else:
                    continue
            else:
                dot_assignments[trait.id] = 1

            num_dots -= 1

        for trait_id, value in dot_assignments.items():
            character_trait = await CharacterTrait.create(
                value=value,
                character=character,
                trait=traits_by_id[trait_id],
            )
            await self.character_trait_service.after_save(character_trait, character)

    async def _generate_merit_background_values(self, character: Character) -> None:
        """Randomly generate merit and background values for the character."""
        backgrounds_category, merits_category = await asyncio.gather(
            TraitCategory.filter(name="Backgrounds").first(),
            TraitCategory.filter(name="Merits").first(),
        )

        possible_traits = list(
            await Trait.filter(
                category_id__in=[backgrounds_category.id, merits_category.id],
                character_classes__contains=[character.character_class],
                is_archived=False,
                custom_for_character_id__isnull=True,
            )
        )

        await self._distribute_dots_across_traits(
            character, possible_traits, ADVANTAGE_STARTING_DOTS[self.experience_level]
        )

    async def _generate_flaw_values(self, character: Character) -> None:
        """Randomly generate flaw values for the character."""
        flaws_category = await TraitCategory.filter(name="Flaws").first()

        possible_flaws = list(
            await Trait.filter(
                category_id=flaws_category.id,
                character_classes__contains=[character.character_class],
                is_archived=False,
                custom_for_character_id__isnull=True,
            )
        )

        await self._distribute_dots_across_traits(
            character, possible_flaws, FLAW_STARTING_DOTS[self.experience_level]
        )
