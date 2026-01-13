"""Unit tests for the chargen domain."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, ClassVar

import pytest
from beanie.operators import In

from vapi.constants import CharacterClass, CharacterType, GameVersion, HunterCreed
from vapi.db.models import (
    Character,
    CharacterConcept,
    CharacterTrait,
    Trait,
    VampireClan,
    WerewolfAuspice,
    WerewolfTribe,
)
from vapi.db.models.character import VampireAttributes, WerewolfAttributes
from vapi.domain.handlers.character_autogeneration.constants import (
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
from vapi.domain.handlers.character_autogeneration.handler import CharacterAutogenerationHandler

if TYPE_CHECKING:
    from collections.abc import Callable

    from vapi.db.models import Campaign, Company, User


pytestmark = pytest.mark.anyio


class TestGenerateCharacter:
    """Test the generate_character method."""

    character_concepts: ClassVar[list[CharacterConcept]] = []

    @pytest.mark.parametrize(
        ("character_class"),
        CharacterClass,
    )
    async def test_generate_base_character_for_each_class(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        character_class: CharacterClass | None,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify base character generation with various parameter combinations."""
        # Given a chargen instance and optional concept
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )

        # When generating a base character with the provided parameters
        character = await chargen._generate_base_character(
            char_class=character_class,
            character_type=CharacterType.PLAYER,
        )

        # Then verify the character has the correct properties
        db_character = await Character.get(character.id)
        assert db_character.is_chargen is True
        assert db_character.character_class == character_class

        # Cleanup
        await character.delete()

    @pytest.mark.parametrize(
        ("experience_level"),
        AutoGenExperienceLevel,
    )
    async def test_generate_base_character_for_each_experience_level(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        experience_level: AutoGenExperienceLevel,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify base character generation with various parameter combinations."""
        # Given a chargen instance and optional concept
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )

        # When generating a base character with the provided parameters
        character = await chargen._generate_base_character(
            experience_level=experience_level,
            character_type=CharacterType.PLAYER,
        )

        # Then verify the character has the correct properties
        db_character = await Character.get(character.id)
        assert db_character.is_chargen is True
        assert chargen.experience_level == experience_level

        # Cleanup
        await character.delete()

    @pytest.mark.parametrize(
        ("skill_focus"),
        AbilityFocus,
    )
    async def test_generate_base_character_for_each_skill_focus(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        skill_focus: AbilityFocus,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify base character generation with various parameter combinations."""
        # Given a chargen instance and optional concept
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )

        # When generating a base character with the provided parameters
        character = await chargen._generate_base_character(
            skill_focus=skill_focus,
            character_type=CharacterType.PLAYER,
        )

        # Then verify the character has the correct properties
        db_character = await Character.get(character.id)
        assert db_character.is_chargen is True
        assert chargen.skill_focus == skill_focus

        # Cleanup
        await character.delete()

    @pytest.mark.parametrize(
        ("character_type"),
        CharacterType,
    )
    async def test_generate_base_character_for_each_character_type(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        character_type: CharacterType,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify base character generation with various parameter combinations."""
        # Given a chargen instance and optional concept
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )

        # When generating a base character with the provided parameters
        character = await chargen._generate_base_character(
            character_type=character_type,
        )

        # Then verify the character has the correct properties
        db_character = await Character.get(character.id)
        assert db_character.is_chargen is True
        assert db_character.type == character_type

        # Cleanup
        await character.delete()

    @pytest.mark.repeat(10)
    async def test_generate_base_character_with_concept(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify base character generation with various parameter combinations."""
        # Given a chargen instance and optional concept
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )

        if not self.character_concepts:
            self.character_concepts = await CharacterConcept.find(
                CharacterConcept.is_archived == False
            ).to_list()

        concept_to_pass = random.choice(self.character_concepts)

        # When generating a base character with the provided parameters
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            concept=concept_to_pass,
        )

        # Then verify the character has the correct properties
        db_character = await Character.get(character.id)

        assert db_character.is_chargen is True
        assert db_character.concept_id == concept_to_pass.id

        # Cleanup
        await character.delete()


class TestGenerateAttributeValues:
    """Test the generate_attribute_values method."""

    @pytest.mark.parametrize(
        "experience_level",
        [
            (AutoGenExperienceLevel.NEW),
            (AutoGenExperienceLevel.INTERMEDIATE),
            (AutoGenExperienceLevel.ADVANCED),
            (AutoGenExperienceLevel.ELITE),
        ],
    )
    async def test_generate_attribute_values(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        all_traits_in_section: Callable[[str], list[Trait]],
        experience_level: AutoGenExperienceLevel,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify attribute values are generated with correct sum for experience level."""
        # Given a character with a specific experience level
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER, experience_level=experience_level
        )

        # When generating the attribute values
        await chargen._generate_attribute_values(character)
        await character.sync()

        # Then verify the sum of attribute trait values matches expected distribution
        attribute_traits = await all_traits_in_section("Attributes")
        character_attribute_traits = await CharacterTrait.find(
            CharacterTrait.character_id == character.id,
            In(CharacterTrait.trait.id, [trait.id for trait in attribute_traits]),
            fetch_links=True,
        ).to_list()

        assert len(character_attribute_traits) == 9

        expected_sum = sum(ATTRIBUTE_DOT_DISTRIBUTION) + getattr(
            ATTRIBUTE_DOT_BONUS, experience_level.name
        )
        sum_of_character_traits = sum([trait.value for trait in character_attribute_traits])

        assert sum_of_character_traits == expected_sum


class TestGenerateWillpowerValue:
    """Test the generate_willpower_value method."""

    async def test_do_not_set_willpower_value_for_v5_characters(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify willpower value is not set for V5 characters."""
        # Given a character with a V5 game version
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER, game_version=GameVersion.V5
        )
        await chargen._generate_willpower_value(character)
        await character.sync()
        assert character.character_trait_ids == []
        assert not await CharacterTrait.find_one(
            CharacterTrait.character_id == character.id,
            CharacterTrait.trait.name == "Willpower",
            fetch_links=True,
        )

    async def test_generate_willpower_value_for_v4_characters(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify willpower value is zero when composure and resolve are not set."""
        # Given a character without composure and resolve traits
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER, game_version=GameVersion.V4
        )

        # When generating the willpower value
        await chargen._generate_willpower_value(character)
        await character.sync()

        # Then verify willpower is zero
        willpower = await CharacterTrait.find_one(
            CharacterTrait.character_id == character.id,
            CharacterTrait.trait.name == "Willpower",  # type: ignore [attr-defined]
            fetch_links=True,
        )
        assert willpower.value in [3, 4, 5, 6, 7]


class TestGenerateAbilityValues:
    """Test the generate_ability_values method."""

    @pytest.mark.parametrize(
        ("experience_level", "skill_focus"),
        [
            (AutoGenExperienceLevel.NEW, AbilityFocus.JACK_OF_ALL_TRADES),
            (AutoGenExperienceLevel.INTERMEDIATE, AbilityFocus.BALANCED),
            (AutoGenExperienceLevel.ADVANCED, AbilityFocus.SPECIALIST),
            (AutoGenExperienceLevel.ELITE, AbilityFocus.JACK_OF_ALL_TRADES),
            (AutoGenExperienceLevel.NEW, AbilityFocus.JACK_OF_ALL_TRADES),  # noqa: PT014
        ],
    )
    async def test_generate_ability_values(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        all_traits_in_section: Callable[[str], list[Trait]],
        experience_level: AutoGenExperienceLevel,
        skill_focus: AbilityFocus,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify ability values are generated with correct sum for experience level and skill focus."""
        # Given a character with a specific experience level and skill focus
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            experience_level=experience_level,
            skill_focus=skill_focus,
        )

        # When generating the ability values
        await chargen._generate_ability_values(character)
        await character.sync()

        # Then verify the sum of ability trait values matches expected distribution
        ability_traits = await all_traits_in_section("Abilities")
        character_ability_traits = await CharacterTrait.find(
            CharacterTrait.character_id == character.id,
            In(CharacterTrait.trait.id, [trait.id for trait in ability_traits]),
            fetch_links=True,
        ).to_list()

        sum_of_character_traits = sum([trait.value for trait in character_ability_traits])

        expected_sum = sum(ABILITY_FOCUS_DOT_DISTRIBUTION[skill_focus]) + getattr(
            ABILITY_DOT_BONUS, experience_level.name
        )
        assert sum_of_character_traits == expected_sum

        # Cleanup
        await character.delete()


class TestGenerateVampireAttributes:
    """Test the generate_vampire_attributes method."""

    @pytest.mark.parametrize(
        "character_class",
        [
            x
            for x in list[CharacterClass](CharacterClass)
            if x
            not in {
                CharacterClass.VAMPIRE,
                CharacterClass.GHOUL,
            }
        ],
    )
    async def test_vampire_attributes_skipped(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        character_class: CharacterClass,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify vampire attributes are not generated for non-vampire characters."""
        # Given a character with a non-vampire class
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER, char_class=character_class
        )
        assert character.vampire_attributes == VampireAttributes() or None

        # When generating the vampire attributes
        character = await chargen._generate_vampire_attributes(character)

        # Then verify the vampire attributes are not generated
        assert character.vampire_attributes == VampireAttributes() or None

        # Cleanup
        await character.delete()

    async def test_random_vampire_attributes_generated(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        all_traits_in_category: Callable[[str], list[Trait]],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify vampire attributes are generated for vampire characters."""
        # Given a character with a vampire class
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER, char_class=CharacterClass.VAMPIRE
        )

        # When generating the vampire attributes
        character = await chargen._generate_vampire_attributes(character)

        # Then verify the vampire attributes are generated
        vampire_clans = await VampireClan.find(VampireClan.is_archived == False).to_list()
        assert character.vampire_attributes.clan_name in [x.name for x in vampire_clans]
        assert character.vampire_attributes.clan_id in [x.id for x in vampire_clans]

        # And verify the disciplines are generated
        all_disciplines = await all_traits_in_category("Disciplines")
        character_disciplines = await CharacterTrait.find(
            CharacterTrait.character_id == character.id,
            In(CharacterTrait.trait.id, [trait.id for trait in all_disciplines]),
            fetch_links=True,
        ).to_list()
        character_clan = await VampireClan.get(character.vampire_attributes.clan_id)
        for trait_id in character_clan.discipline_ids:
            assert trait_id in [trait.trait.id for trait in character_disciplines]

    @pytest.mark.parametrize(
        "experience_level",
        [
            (AutoGenExperienceLevel.NEW),
            (AutoGenExperienceLevel.INTERMEDIATE),
            (AutoGenExperienceLevel.ADVANCED),
            (AutoGenExperienceLevel.ELITE),
        ],
    )
    async def test_extra_disciplines_generated(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        all_traits_in_category: Callable[[str], list[Trait]],
        experience_level: AutoGenExperienceLevel,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify extra disciplines are generated for vampire characters."""
        # Given a character with a vampire class
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            char_class=CharacterClass.VAMPIRE,
            experience_level=experience_level,
        )

        # When generating the vampire attributes
        character = await chargen._generate_vampire_attributes(character)

        # Then verify the extra disciplines are generated
        all_disciplines = await all_traits_in_category("Disciplines")
        clan_discipline_ids = (
            await VampireClan.get(character.vampire_attributes.clan_id)
        ).discipline_ids
        character_disciplines = await CharacterTrait.find(
            CharacterTrait.character_id == character.id,
            In(CharacterTrait.trait.id, [trait.id for trait in all_disciplines]),
            fetch_links=True,
        ).to_list()
        assert (
            len(character_disciplines)
            == len(clan_discipline_ids) + EXTRA_DISCIPLINES_MAP[experience_level]
        )

    @pytest.mark.parametrize(
        "clan_name",
        [
            ("Assamite"),
            ("Banu Haqim"),
            ("Toreador"),
            ("Tremere"),
            ("Ventrue"),
            ("Lasombra"),
            ("Nosferatu"),
            ("Tzimisce"),
        ],
    )
    async def test_set_clan(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        all_traits_in_category: Callable[[str], list[Trait]],
        clan_name: str,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify the clan is selected correctly."""
        # Given a character with a vampire class
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        vampire_clan = await VampireClan.find_one(VampireClan.name == clan_name)
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            char_class=CharacterClass.VAMPIRE,
        )
        character = await chargen._generate_vampire_attributes(
            character=character, vampire_clan=vampire_clan
        )
        assert character.vampire_attributes.clan_name == clan_name


class TestGenerateWerewolfAttributes:
    """Test the generate_werewolf_attributes method."""

    async def test_werewolf_attributes_skipped_for_non_werewolf_characters(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify werewolf attributes are not generated for non-werewolf characters."""
        # Given a character with a non-werewolf class
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        for character_class in [
            x for x in list[CharacterClass](CharacterClass) if x not in {CharacterClass.WEREWOLF}
        ]:
            character = await chargen._generate_base_character(
                character_type=CharacterType.PLAYER, char_class=character_class
            )
            character = await chargen._generate_werewolf_attributes(character)
            assert character.werewolf_attributes == WerewolfAttributes()

    async def test_random_werewolf_attributes_generated(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        all_traits_in_category: Callable[[str], list[Trait]],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify werewolf attributes are generated for werewolf characters."""
        # Given a character with a werewolf class
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            char_class=CharacterClass.WEREWOLF,
        )
        character = await chargen._generate_werewolf_attributes(character)
        werewolf_tribes = await WerewolfTribe.find(WerewolfTribe.is_archived == False).to_list()
        werewolf_auspices = await WerewolfAuspice.find(
            WerewolfAuspice.is_archived == False
        ).to_list()
        assert character.werewolf_attributes.tribe_name in [x.name for x in werewolf_tribes]
        assert character.werewolf_attributes.tribe_id in [x.id for x in werewolf_tribes]
        assert character.werewolf_attributes.auspice_name in [x.name for x in werewolf_auspices]
        assert character.werewolf_attributes.auspice_id in [x.id for x in werewolf_auspices]

        # And verify the tribe and auspice are generated
        auspice = await WerewolfAuspice.get(character.werewolf_attributes.auspice_id)
        assert auspice.name in [x.name for x in werewolf_auspices]

        tribe = await WerewolfTribe.get(character.werewolf_attributes.tribe_id)
        assert tribe.name in [x.name for x in werewolf_tribes]

        # And verify the rage trait is generated
        rage_trait = await Trait.find_one(Trait.name == "Rage")
        rage_character_trait = await CharacterTrait.find_one(
            CharacterTrait.character_id == character.id,
            CharacterTrait.trait.id == rage_trait.id,
        )
        assert rage_character_trait.value in range(1, 5)

        # And verify the renown traits are generated
        renown_traits = await CharacterTrait.find(
            CharacterTrait.character_id == character.id,
            In(
                CharacterTrait.trait.name,
                [
                    "Honor",
                    "Wisdom",
                    "Glory",
                ],
            ),
            fetch_links=True,
        ).to_list()
        assert len(renown_traits) == 3
        assert sum([trait.value for trait in renown_traits]) == 3

    @pytest.mark.parametrize(
        "tribe_name",
        [
            ("Hart Wardens"),
            ("Black Furies"),
            ("Bone Gnawers"),
            ("Children of Gaia"),
        ],
    )
    async def test_set_tribe(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        all_traits_in_category: Callable[[str], list[Trait]],
        tribe_name: str,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify the tribe is selected correctly."""
        # Given a character with a werewolf class
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        werewolf_tribe = await WerewolfTribe.find_one(WerewolfTribe.name == tribe_name)
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER, char_class=CharacterClass.WEREWOLF
        )
        character = await chargen._generate_werewolf_attributes(
            character, werewolf_tribe=werewolf_tribe
        )
        assert character.werewolf_attributes.tribe_name == tribe_name
        assert character.werewolf_attributes.tribe_id == werewolf_tribe.id

    @pytest.mark.parametrize(
        "auspice_name",
        [
            ("Ragabash"),
            ("Galliard"),
            ("Ahroun"),
            ("Philodox"),
        ],
    )
    async def test_set_auspice(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        all_traits_in_category: Callable[[str], list[Trait]],
        auspice_name: str,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify the auspice is selected correctly."""
        # Given a character with a werewolf class
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        werewolf_auspice = await WerewolfAuspice.find_one(WerewolfAuspice.name == auspice_name)
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER, char_class=CharacterClass.WEREWOLF
        )
        character = await chargen._generate_werewolf_attributes(
            character, werewolf_auspice=werewolf_auspice
        )
        assert character.werewolf_attributes.auspice_name == auspice_name
        assert character.werewolf_attributes.auspice_id == werewolf_auspice.id

    @pytest.mark.parametrize(
        ("auspice_name", "tribe_name", "experience_level"),
        [
            ("Ragabash", "Hart Wardens", AutoGenExperienceLevel.NEW),
            ("Galliard", "Black Furies", AutoGenExperienceLevel.INTERMEDIATE),
            ("Ahroun", "Bone Gnawers", AutoGenExperienceLevel.ADVANCED),
            ("Philodox", "Children of Gaia", AutoGenExperienceLevel.ELITE),
        ],
    )
    async def test_generate_werewolf_gifts_and_rites(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        debug: Callable[[Any], None],
        auspice_name: str,
        tribe_name: str,
        experience_level: AutoGenExperienceLevel,
    ) -> None:
        """Verify werewolf gifts and rites are generated for werewolf characters."""
        # Given a character
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        werewolf_tribe = await WerewolfTribe.find_one(WerewolfTribe.name == tribe_name)
        werewolf_auspice = await WerewolfAuspice.find_one(WerewolfAuspice.name == auspice_name)
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            char_class=CharacterClass.WEREWOLF,
            experience_level=experience_level,
        )
        character = await chargen._generate_werewolf_attributes(
            character, werewolf_tribe=werewolf_tribe, werewolf_auspice=werewolf_auspice
        )
        character = await chargen._generate_werewolf_gifts_and_rites(character)
        # debug(character.werewolf_attributes.gift_ids)

        gift_id_modifiers = EXTRA_WEREWOLF_GIFT_MAP

        assert (
            len(character.werewolf_attributes.gift_ids) == 3 + gift_id_modifiers[experience_level]
        )

        assert (
            len(character.werewolf_attributes.rite_ids) == NUM_WEREWOLF_RITE_MAP[experience_level]
        )


class TestGenerateHunterAttributes:
    """Test the generate_hunter_attributes method."""

    @pytest.mark.parametrize(
        "experience_level",
        [
            (AutoGenExperienceLevel.NEW),
            (AutoGenExperienceLevel.INTERMEDIATE),
            (AutoGenExperienceLevel.ADVANCED),
            (AutoGenExperienceLevel.ELITE),
        ],
    )
    async def test_hunter_attributes_generated(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        experience_level: AutoGenExperienceLevel,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify hunter attributes are generated for character."""
        # Given a range of starting edges and perks b/c characters can start with either 1 or 2 of either
        expected_num_edges = [
            1 + EXTRA_HUNTER_EDGE_MAP[experience_level],
            2 + EXTRA_HUNTER_EDGE_MAP[experience_level],
        ]
        expected_num_perks = [
            1 + EXTRA_HUNTER_EDGE_PERK_MAP[experience_level],
            2 + EXTRA_HUNTER_EDGE_PERK_MAP[experience_level],
        ]

        # Given a character
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            experience_level=experience_level,
            char_class=CharacterClass.HUNTER,
        )
        character = await chargen._generate_hunter_attributes(character)
        await character.sync()

        # Then verify the hunter attributes are generated
        assert character.hunter_attributes.creed in [x.value.title() for x in list(HunterCreed)]

        # debug(character.hunter_attributes.model_dump(mode="json"))
        # debug(expected_num_edges, "expected_num_edges")
        # debug(expected_num_perks, "expected_num_perks")
        assert len(character.hunter_attributes.edges) in expected_num_edges

        total_perks = sum([len(edge.perk_ids) for edge in character.hunter_attributes.edges])
        assert total_perks in expected_num_perks


class TestGenerateAdvantageValues:
    """Test the generate_advantage_values method."""

    @pytest.mark.parametrize(
        "experience_level",
        [
            (AutoGenExperienceLevel.NEW),
            (AutoGenExperienceLevel.INTERMEDIATE),
            (AutoGenExperienceLevel.ADVANCED),
            (AutoGenExperienceLevel.ELITE),
        ],
    )
    async def test_advantage_values_generated(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        all_traits_in_category: Callable[[str], list[Trait]],
        experience_level: AutoGenExperienceLevel,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify advantage values are generated for character."""
        # Given a character
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            experience_level=experience_level,
        )

        # When generating the advantage values
        await chargen._generate_merit_background_values(character)
        await character.sync()

        # Then verify the advantage values are generated
        backgrounds = await all_traits_in_category("Backgrounds")
        merits = await all_traits_in_category("Merits")
        all_traits = backgrounds + merits
        character_traits = await CharacterTrait.find(
            CharacterTrait.character_id == character.id,
            In(CharacterTrait.trait.id, [trait.id for trait in all_traits]),
            fetch_links=True,
        ).to_list()

        assert sum([trait.value for trait in character_traits]) == getattr(
            ADVANTAGE_STARTING_DOTS, experience_level.name
        )


class TestGenerateFlawValues:
    """Test the generate_flaw_values method."""

    @pytest.mark.parametrize(
        "experience_level",
        [
            (AutoGenExperienceLevel.NEW),
            (AutoGenExperienceLevel.INTERMEDIATE),
            (AutoGenExperienceLevel.ADVANCED),
            (AutoGenExperienceLevel.ELITE),
        ],
    )
    async def test_flaw_values_generated(
        self,
        base_company: Company,
        base_user: User,
        base_campaign: Campaign,
        all_traits_in_category: Callable[[str], list[Trait]],
        experience_level: AutoGenExperienceLevel,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify flaw values are generated for character."""
        # Given a character
        chargen = CharacterAutogenerationHandler(
            company=base_company,
            user=base_user,
            campaign=base_campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            experience_level=experience_level,
        )

        # When generating the flaw values
        await chargen._generate_flaw_values(character)
        await character.sync()

        # Then verify the flaw values are generated
        flaws = await all_traits_in_category("Flaws")
        character_traits = await CharacterTrait.find(
            CharacterTrait.character_id == character.id,
            In(CharacterTrait.trait.id, [trait.id for trait in flaws]),
            fetch_links=True,
        ).to_list()
        assert sum([trait.value for trait in character_traits]) == getattr(
            FLAW_STARTING_DOTS, experience_level.name
        )
