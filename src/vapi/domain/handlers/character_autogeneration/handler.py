"""RNG character generation library."""

import logging
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from beanie.operators import In, Or
from faker import Faker
from numpy import int32
from numpy.random import default_rng

from vapi.constants import CharacterClass, CharacterType, GameVersion, HunterCreed
from vapi.db.models import (
    AdvantageCategory,
    Campaign,
    Character,
    CharacterConcept,
    CharacterTrait,
    CharSheetSection,
    Company,
    HunterEdge,
    Trait,
    TraitCategory,
    User,
    VampireClan,
    WerewolfAuspice,
    WerewolfGift,
    WerewolfRite,
    WerewolfTribe,
)
from vapi.db.models.character import (
    HunterAttributes,
    HunterAttributesEdgeModel,
    MageAttributes,
    VampireAttributes,
    WerewolfAttributes,
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
    from beanie import PydanticObjectId

fake = Faker()

_rng = default_rng()

logger = logging.getLogger("vapi")


@dataclass
class TraitCategoryDotDistribution:
    """Trait Category dot distribution for RNG character generation."""

    primary: int
    secondary: int
    tertiary: int
    unknown: int = 0


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
        campaign: Campaign = None,
    ) -> None:
        self.company = company
        self.user = user
        self.experience_level: AutoGenExperienceLevel = None
        self.campaign = campaign
        self.skill_focus: AbilityFocus = None
        self.concept: CharacterConcept = None
        self.character_trait_service = CharacterTraitService()

    async def generate_character(  # noqa: PLR0913
        self,
        character_type: CharacterType,
        experience_level: AutoGenExperienceLevel = None,
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
        character = await self._generate_base_character(
            character_type, experience_level, skill_focus, char_class, concept
        )

        # Generate class-specific attributes
        match character.character_class:
            case CharacterClass.VAMPIRE:
                character = await self._generate_vampire_attributes(character, vampire_clan)
            case CharacterClass.WEREWOLF:
                character = await self._generate_werewolf_attributes(
                    character, werewolf_tribe, werewolf_auspice
                )
                character = await self._generate_werewolf_gifts_and_rites(character)
            case CharacterClass.HUNTER:
                character = await self._generate_hunter_attributes(character)

        # Generate base traits
        await self._generate_attribute_values(character)
        await self._generate_ability_values(character)
        await self._generate_willpower_value(character)
        await self._generate_merit_background_values(character)
        await self._generate_flaw_values(character)
        await self._generate_humanity_value(character)

        await character.sync()
        return character

    async def _generate_base_character(
        self,
        character_type: CharacterType,
        experience_level: AutoGenExperienceLevel = None,
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
        self.skill_focus = (
            skill_focus if skill_focus else random.choice(list[AbilityFocus](AbilityFocus))
        )
        self.experience_level = experience_level if experience_level else AutoGenExperienceLevel.NEW

        name_first, name_last = await generate_unique_name(self.company.id)

        if char_class is None:
            char_class = get_character_class_from_percentile()

        if concept is None:
            concept = random.choice(
                await CharacterConcept.find(
                    Or(
                        CharacterConcept.company_id == self.company.id,
                        CharacterConcept.company_id == None,
                    ),
                    CharacterConcept.is_archived == False,
                ).to_list()
            )

        self.concept = concept

        character = Character(
            is_chargen=True,
            name_first=name_first,
            name_last=name_last,
            character_class=char_class,
            concept_id=concept.id,
            company_id=self.company.id,
            campaign_id=self.campaign.id if self.campaign else None,
            type=character_type,
            game_version=game_version,
            user_creator_id=self.user.id,
            user_player_id=self.user.id,
            vampire_attributes=VampireAttributes(),
            werewolf_attributes=WerewolfAttributes(),
            mage_attributes=MageAttributes(),
            hunter_attributes=HunterAttributes(),
        )

        await character.insert()
        return character

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

        attribute_section = await CharSheetSection.find_one(CharSheetSection.name == "Attributes")
        categories = await TraitCategory.find(
            TraitCategory.parent_sheet_section_id == attribute_section.id,
            TraitCategory.character_classes == character.character_class,
            TraitCategory.game_versions == character.game_version,
            TraitCategory.is_archived == False,
        ).to_list()
        shuffled_categories = random.sample(categories, len(categories))

        for category in shuffled_categories:
            category_traits = await Trait.find(
                Trait.parent_category_id == category.id,
                Trait.character_classes == character.character_class,
                Trait.game_versions == character.game_version,
                Trait.is_archived == False,
                Trait.custom_for_character_id == None,
            ).to_list()

            for t in category_traits:
                character_trait = CharacterTrait(
                    value=dots_to_apply.pop(0),
                    character_id=character.id,
                    trait=t,
                )
                await character_trait.insert()
                await self.character_trait_service.after_save(character_trait)

    async def _generate_willpower_value(self, character: Character) -> None:
        """Randomly generate willpower value for the character.

        Generate and assign random willpower value for the given character based on their concept, class, and experience level.

        Args:
            character (Character): The character for which to generate willpower value.
        """
        if character.game_version != GameVersion.V4:
            return

        willpower_trait = await Trait.find_one(Trait.name == "Willpower")
        character_trait = CharacterTrait(
            value=random.randint(3, 7),
            character_id=character.id,
            trait=willpower_trait,
        )
        await character_trait.insert()
        await self.character_trait_service.after_save(character_trait)

    async def _generate_humanity_value(self, character: Character) -> None:
        """Randomly generate humanity value for the character.

        Generate and assign random humanity value for the given character based on their concept, class, and experience level.

        Args:
            character (Character): The character for which to generate humanity value.
        """
        humanity_trait = await Trait.find_one(Trait.name == "Humanity")
        if character.character_class not in humanity_trait.character_classes:
            return

        character_trait = CharacterTrait(
            value=7,
            character_id=character.id,
            trait=humanity_trait,
        )
        await character_trait.insert()
        await self.character_trait_service.after_save(character_trait)

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

        ability_section = await CharSheetSection.find_one(CharSheetSection.name == "Abilities")
        categories = await TraitCategory.find(
            TraitCategory.parent_sheet_section_id == ability_section.id,
            TraitCategory.character_classes == character.character_class,
            TraitCategory.game_versions == character.game_version,
            TraitCategory.is_archived == False,
        ).to_list()

        abilities = await Trait.find(
            In(Trait.parent_category_id, [x.id for x in categories]),
            Trait.character_classes == character.character_class,
            Trait.game_versions == character.game_version,
            Trait.is_archived == False,
            Trait.custom_for_character_id == None,
        ).to_list()
        shuffled_abilities = random.sample(abilities, len(abilities))

        for ability_name in self.concept.favored_ability_names:
            trait = await Trait.find_one(Trait.name == ability_name)
            if not trait or trait not in shuffled_abilities:
                continue

            shuffled_abilities.remove(trait)
            if dots_to_apply:
                value = max(dots_to_apply)
                dots_to_apply.remove(value)

            else:
                value = trait.min_value
            character_trait = CharacterTrait(
                value=value,
                character_id=character.id,
                trait=trait,
            )
            await character_trait.insert()

        for ability in shuffled_abilities:
            value = dots_to_apply.pop(0) if dots_to_apply else ability.min_value
            character_trait = CharacterTrait(
                value=value,
                character_id=character.id,
                trait=ability,
            )
            await character_trait.insert()
            await self.character_trait_service.after_save(character_trait)

    async def _generate_vampire_attributes(
        self, character: Character, vampire_clan: VampireClan | None = None
    ) -> Character:
        """Randomly generate vampire attributes for the character.

        Generate and assign random vampire attributes for the given character based on their concept, class, and experience level.

        Args:
            character (Character): The character for which to generate vampire attributes.
            vampire_clan (VampireClan | None): The vampire clan to generate. If None, a random clan will be selected.

        Returns:
            Character: The updated character object with randomly generated vampire attributes.
        """
        if character.character_class not in {CharacterClass.VAMPIRE, CharacterClass.GHOUL}:
            return character

        if not vampire_clan:
            vampire_clan = random.choice(
                await VampireClan.find(VampireClan.is_archived == False).to_list()
            )

        if character.character_class == CharacterClass.VAMPIRE:
            character.vampire_attributes = VampireAttributes(
                clan_id=vampire_clan.id,
                clan_name=vampire_clan.name,
                bane=random.choice([vampire_clan.bane, vampire_clan.variant_bane])
                if vampire_clan.bane and vampire_clan.variant_bane
                else vampire_clan.bane,
                compulsion=vampire_clan.compulsion,
            )
            await character.save()

        disciplines_to_set = []
        for trait_id in vampire_clan.discipline_ids:
            trait = await Trait.get(trait_id)
            if not trait:
                continue
            disciplines_to_set.append(trait)

        disciplines_category = await TraitCategory.find_one(TraitCategory.name == "Disciplines")
        all_disciplines = await Trait.find(
            Trait.parent_category_id == disciplines_category.id,
            Trait.character_classes == character.character_class,
            Trait.game_versions == character.game_version,
            Trait.is_archived == False,
            Trait.custom_for_character_id == None,
        ).to_list()

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
            character_trait = CharacterTrait(
                value=value,
                character_id=character.id,
                trait=discipline,
            )
            await character_trait.insert()
            await self.character_trait_service.after_save(character_trait)

        await character.sync()
        return character

    async def _generate_werewolf_attributes(
        self,
        character: Character,
        werewolf_tribe: WerewolfTribe | None = None,
        werewolf_auspice: WerewolfAuspice | None = None,
    ) -> Character:
        """Randomly generate werewolf attributes for the character.

        Generate and assign random werewolf attributes for the given character based on their concept, class, and experience level.

        Args:
            character (Character): The character for which to generate werewolf attributes.
            werewolf_tribe (WerewolfTribe | None): The werewolf tribe to generate. If None, a random tribe will be selected.
            werewolf_auspice (WerewolfAuspice | None): The werewolf auspice to generate. If None, a random auspice will be selected.

        Returns:
            Character: The updated character object with randomly generated werewolf attributes.
        """
        if character.character_class not in {CharacterClass.WEREWOLF}:
            return character

        if not werewolf_tribe:
            werewolf_tribe = random.choice(
                await WerewolfTribe.find(WerewolfTribe.is_archived == False).to_list()
            )
        if not werewolf_auspice:
            werewolf_auspice = random.choice(
                await WerewolfAuspice.find(WerewolfAuspice.is_archived == False).to_list()
            )

        character.werewolf_attributes = WerewolfAttributes(
            tribe_id=werewolf_tribe.id,
            tribe_name=werewolf_tribe.name,
            auspice_id=werewolf_auspice.id,
            auspice_name=werewolf_auspice.name,
        )
        await character.save()

        # Allocate Rage
        rage_trait = await Trait.find_one(Trait.name == "Rage")
        if rage_trait:
            character_trait = await CharacterTrait(
                value=random.randint(1, 3),
                character_id=character.id,
                trait=rage_trait,
            ).insert()
            await self.character_trait_service.after_save(character_trait)

        # Allocate Renown traits
        honor_trait = await Trait.find_one(Trait.name == "Honor")
        wisdom_trait = await Trait.find_one(Trait.name == "Wisdom")
        glory_trait = await Trait.find_one(Trait.name == "Glory")
        renown_traits = [honor_trait, wisdom_trait, glory_trait]
        tribe_renown_trait = next(
            x for x in renown_traits if x.name.lower() == werewolf_tribe.renown.name.lower()
        )
        not_tribe_renown_traits = [
            x for x in renown_traits if x.name.lower() != werewolf_tribe.renown.name.lower()
        ]
        shuffled_not_tribe_renown_traits = random.sample(
            not_tribe_renown_traits, len(not_tribe_renown_traits)
        )

        value_modifiers = {
            AutoGenExperienceLevel.NEW: 0,
            AutoGenExperienceLevel.INTERMEDIATE: 1,
            AutoGenExperienceLevel.ADVANCED: 2,
            AutoGenExperienceLevel.ELITE: 3,
        }

        character_trait = await CharacterTrait(
            value=2 + value_modifiers[self.experience_level],
            character_id=character.id,
            trait=tribe_renown_trait,
        ).insert()
        await self.character_trait_service.after_save(character_trait)

        for i, trait in enumerate(shuffled_not_tribe_renown_traits):
            character_trait = await CharacterTrait(
                value=i + value_modifiers[self.experience_level],
                character_id=character.id,
                trait=trait,
            ).insert()
            await self.character_trait_service.after_save(character_trait)

        await character.sync()
        return character

    async def _generate_hunter_attributes(self, character: Character) -> Character:
        """Randomly generate hunter attributes for the character.

        Generate and assign random hunter attributes for the given character based on their concept, class, and experience level.
        """
        if character.character_class not in {CharacterClass.HUNTER}:
            return character

        creed = random.choice(list(HunterCreed))

        # New characters select between 2 Edges and 1 Perk or 1 Edge and 2 Perks.
        starting_num_edges = random.choice([2, 1])
        starting_num_perks = 1 if starting_num_edges == 2 else 2  # noqa: PLR2004

        num_edges = starting_num_edges + EXTRA_HUNTER_EDGE_MAP[self.experience_level]
        num_perks = starting_num_perks + EXTRA_HUNTER_EDGE_PERK_MAP[self.experience_level]

        all_edges = await HunterEdge.find(HunterEdge.is_archived == False).to_list()

        selected_edges = []
        for _ in range(num_edges):
            edge = random.choice(all_edges)
            all_edges.remove(edge)
            selected_edges.append(edge)

        character_edges = [
            HunterAttributesEdgeModel(edge_id=edge.id, perk_ids=[]) for edge in selected_edges
        ]

        # Generate perks for the character
        guard = 0
        for _ in range(num_perks):

            def _get_perk(guard: int) -> None:
                if guard > 20:  # noqa: PLR2004
                    logger.error(
                        "Failed to generate perks for character",
                        extra={
                            "character_id": character.id,
                            "num_perks": num_perks,
                            "num_edges": num_edges,
                            "num_tries": guard,
                            "edge_ids": [x.id for x in selected_edges],
                            "component": "domain",
                            "command": "generate_hunter_attributes",
                        },
                    )
                    return

                character_edge = random.choice(character_edges)
                db_edge = next((x for x in selected_edges if x.id == character_edge.edge_id), None)
                if db_edge is None:
                    _get_perk(guard + 1)
                    return

                possible_perk_ids = (
                    [x for x in db_edge.perk_ids if x not in character_edge.perk_ids]
                    if db_edge.perk_ids
                    else []
                )

                if not possible_perk_ids:
                    _get_perk(guard + 1)
                    return

                character_edge.perk_ids.append(random.choice(possible_perk_ids))

            _get_perk(guard)

        character.hunter_attributes = HunterAttributes(
            creed=creed.value.title(),
            edges=character_edges,
        )
        await character.save()

        return character

    async def _generate_werewolf_gifts_and_rites(self, character: Character) -> Character:
        """Randomly generate werewolf gifts for the character.

        Generate and assign random werewolf gifts for the given character based on their concept, class, and experience level.

        Args:
            character (Character): The character for which to generate werewolf gifts.

        Returns:
            Character: The updated character object with randomly generated werewolf gifts.
        """
        if character.character_class not in {CharacterClass.WEREWOLF}:
            return character

        await character.sync()
        total_renown = character.werewolf_attributes.total_renown
        auspice_id = character.werewolf_attributes.auspice_id
        tribe_id = character.werewolf_attributes.tribe_id

        tribe_gifts = await WerewolfGift.find(
            WerewolfGift.tribe_id == tribe_id, WerewolfGift.minimum_renown <= total_renown
        ).to_list()
        auspice_gifts = await WerewolfGift.find(
            WerewolfGift.auspice_id == auspice_id, WerewolfGift.minimum_renown <= total_renown
        ).to_list()
        native_gifts = await WerewolfGift.find(
            WerewolfGift.is_native_gift == True, WerewolfGift.minimum_renown <= total_renown
        ).to_list()
        rites = await WerewolfRite.find().to_list()

        value_modifiers = divide_total_randomly(
            total=EXTRA_WEREWOLF_GIFT_MAP[self.experience_level], num=3, max_value=5
        )

        for _ in range(1 + value_modifiers[0]):
            gift_id = random.choice(
                [x.id for x in tribe_gifts if x.id not in character.werewolf_attributes.gift_ids]
            )
            character.werewolf_attributes.gift_ids.append(gift_id)

        for _ in range(1 + value_modifiers[1]):
            gift_id = random.choice(
                [x.id for x in auspice_gifts if x.id not in character.werewolf_attributes.gift_ids]
            )
            character.werewolf_attributes.gift_ids.append(gift_id)

        for _ in range(1 + value_modifiers[2]):
            gift_id = random.choice(
                [x.id for x in native_gifts if x.id not in character.werewolf_attributes.gift_ids]
            )
            character.werewolf_attributes.gift_ids.append(gift_id)

        for _ in range(NUM_WEREWOLF_RITE_MAP[self.experience_level]):
            rite_id = random.choice(
                [x.id for x in rites if x.id not in character.werewolf_attributes.rite_ids]
            )
            character.werewolf_attributes.rite_ids.append(rite_id)

        await character.save()

        return character

    async def _generate_merit_background_values(self, character: Character) -> None:
        """Randomly generate merit and background values for the character.

        Generate and assign random merit and background values for the given character based on their concept, class, and experience level.

        Args:
            character (Character): The character for which to generate merit and background values.
        """
        backgrounds_category = await TraitCategory.find_one(TraitCategory.name == "Backgrounds")
        merits_category = await TraitCategory.find_one(TraitCategory.name == "Merits")

        possible_traits = await Trait.find(
            In(Trait.parent_category_id, [backgrounds_category.id, merits_category.id]),
            Trait.character_classes == character.character_class,
            Trait.is_archived == False,
            Trait.custom_for_character_id == None,
        ).to_list()

        num_dots = getattr(ADVANTAGE_STARTING_DOTS, self.experience_level.name)
        traits_to_set: dict[PydanticObjectId, int] = {}

        while num_dots > 0:
            trait = random.choice(possible_traits)

            if trait.advantage_category_id:
                advantage_category = await AdvantageCategory.get(trait.advantage_category_id)
                if advantage_category.requires_parent:
                    parent_trait = await Trait.find_one(Trait.name == advantage_category.name)
                    if parent_trait.id not in traits_to_set or traits_to_set[parent_trait.id] < min(
                        parent_trait.max_value, 2
                    ):
                        trait = parent_trait

            if trait.id in traits_to_set:
                if traits_to_set[trait.id] < trait.max_value:
                    traits_to_set[trait.id] += 1
                else:
                    continue
            else:
                traits_to_set[trait.id] = 1

            num_dots -= 1

        for trait_id, value in traits_to_set.items():
            trait = await Trait.get(trait_id)
            character_trait = CharacterTrait(
                value=value,
                character_id=character.id,
                trait=trait,
            )
            await character_trait.insert()
            await self.character_trait_service.after_save(character_trait)

    async def _generate_flaw_values(self, character: Character) -> None:
        """Randomly generate flaw values for the character.

        Generate and assign random flaw values for the given character based on their concept, class, and experience level.

        Args:
            character (Character): The character for which to generate flaw values.
        """
        flaws_category = await TraitCategory.find_one(TraitCategory.name == "Flaws")

        possible_flaws = await Trait.find(
            Trait.parent_category_id == flaws_category.id,
            Trait.character_classes == character.character_class,
            Trait.is_archived == False,
            Trait.custom_for_character_id == None,
        ).to_list()

        num_dots = getattr(FLAW_STARTING_DOTS, self.experience_level.name)
        traits_to_set: dict[PydanticObjectId, int] = {}

        while num_dots > 0:
            trait = random.choice(possible_flaws)

            if trait.advantage_category_id:
                advantage_category = await AdvantageCategory.get(trait.advantage_category_id)
                if advantage_category.requires_parent:
                    parent_trait = await Trait.find_one(Trait.name == advantage_category.name)
                    if not CharacterTrait.find_one(
                        CharacterTrait.character_id == character.id,
                        CharacterTrait.trait.id == parent_trait.id,  # type: ignore [attr-defined]
                        fetch_links=True,
                    ):
                        continue

            if trait.id in traits_to_set:
                if traits_to_set[trait.id] < trait.max_value:
                    traits_to_set[trait.id] += 1
                else:
                    continue
            else:
                traits_to_set[trait.id] = 1

            num_dots -= 1

        for trait_id, value in traits_to_set.items():
            trait = await Trait.get(trait_id)
            character_trait = CharacterTrait(
                value=value,
                character_id=character.id,
                trait=trait,
            )
            await character_trait.insert()
            await self.character_trait_service.after_save(character_trait)
