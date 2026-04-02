"""Unit tests for the chargen domain."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, ClassVar

import pytest

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


pytestmark = pytest.mark.anyio


async def _all_traits_in_section(section_name: str) -> list[Trait]:
    """Return all non-archived traits belonging to a character sheet section."""
    section = await CharSheetSection.filter(name=section_name).first()
    categories = await TraitCategory.filter(
        sheet_section_id=section.id,
        is_archived=False,
    )
    return list(
        await Trait.filter(
            category_id__in=[c.id for c in categories],
            is_archived=False,
        )
    )


async def _all_traits_in_category(category_name: str) -> list[Trait]:
    """Return all non-archived traits belonging to a trait category."""
    category = await TraitCategory.filter(name=category_name).first()
    return list(
        await Trait.filter(
            category_id=category.id,
            is_archived=False,
        )
    )


class TestGenerateCharacter:
    """Test the generate_character method."""

    character_concepts: ClassVar[list[CharacterConcept]] = []

    @pytest.mark.parametrize(
        ("character_class"),
        CharacterClass,
    )
    async def test_generate_base_character_for_each_class(
        self,
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        character_class: CharacterClass | None,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify base character generation with various parameter combinations."""
        # Given a chargen instance
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )

        # When generating a base character with the provided parameters
        character = await chargen._generate_base_character(
            char_class=character_class,
            character_type=CharacterType.PLAYER,
        )

        # Then verify the character has the correct properties
        db_character = await Character.filter(id=character.id).first()
        assert db_character.is_chargen is True
        assert db_character.character_class == character_class

    @pytest.mark.parametrize(
        ("experience_level"),
        AutoGenExperienceLevel,
    )
    async def test_generate_base_character_for_each_experience_level(
        self,
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        experience_level: AutoGenExperienceLevel,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify base character generation with various parameter combinations."""
        # Given a chargen instance
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )

        # When generating a base character with the provided parameters
        character = await chargen._generate_base_character(
            experience_level=experience_level,
            character_type=CharacterType.PLAYER,
        )

        # Then verify the character has the correct properties
        db_character = await Character.filter(id=character.id).first()
        assert db_character.is_chargen is True
        assert chargen.experience_level == experience_level

    @pytest.mark.parametrize(
        ("skill_focus"),
        AbilityFocus,
    )
    async def test_generate_base_character_for_each_skill_focus(
        self,
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        skill_focus: AbilityFocus,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify base character generation with various parameter combinations."""
        # Given a chargen instance
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )

        # When generating a base character with the provided parameters
        character = await chargen._generate_base_character(
            skill_focus=skill_focus,
            character_type=CharacterType.PLAYER,
        )

        # Then verify the character has the correct properties
        db_character = await Character.filter(id=character.id).first()
        assert db_character.is_chargen is True
        assert chargen.skill_focus == skill_focus

    @pytest.mark.parametrize(
        ("character_type"),
        CharacterType,
    )
    async def test_generate_base_character_for_each_character_type(
        self,
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        character_type: CharacterType,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify base character generation with various parameter combinations."""
        # Given a chargen instance
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )

        # When generating a base character with the provided parameters
        character = await chargen._generate_base_character(
            character_type=character_type,
        )

        # Then verify the character has the correct properties
        db_character = await Character.filter(id=character.id).first()
        assert db_character.is_chargen is True
        assert db_character.type == character_type

    @pytest.mark.repeat(10)
    async def test_generate_base_character_with_concept(
        self,
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify base character generation with various parameter combinations."""
        # Given a chargen instance and optional concept
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )

        if not self.character_concepts:
            self.character_concepts = list(await CharacterConcept.filter(is_archived=False))

        concept_to_pass = random.choice(self.character_concepts)

        # When generating a base character with the provided parameters
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            concept=concept_to_pass,
        )

        # Then verify the character has the correct properties
        db_character = await Character.filter(id=character.id).first()

        assert db_character.is_chargen is True
        assert db_character.concept_id == concept_to_pass.id


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
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        experience_level: AutoGenExperienceLevel,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify attribute values are generated with correct sum for experience level."""
        # Given a character with a specific experience level
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER, experience_level=experience_level
        )

        # When generating the attribute values
        await chargen._generate_attribute_values(character)

        # Then verify the sum of attribute trait values matches expected distribution
        attribute_traits = await _all_traits_in_section("Attributes")
        character_attribute_traits = await CharacterTrait.filter(
            character=character,
            trait_id__in=[trait.id for trait in attribute_traits],
        )

        assert len(character_attribute_traits) == 9

        expected_sum = sum(ATTRIBUTE_DOT_DISTRIBUTION) + ATTRIBUTE_DOT_BONUS[experience_level]
        sum_of_character_traits = sum([trait.value for trait in character_attribute_traits])

        assert sum_of_character_traits == expected_sum


class TestGenerateWillpowerValue:
    """Test the generate_willpower_value method."""

    async def test_do_not_set_willpower_value_for_v5_characters(
        self,
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify willpower value is not set for V5 characters."""
        # Given a character with a V5 game version
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER, game_version=GameVersion.V5
        )
        await chargen._generate_willpower_value(character)

        # Then verify no traits were created
        character_traits = await CharacterTrait.filter(character=character)
        assert len(character_traits) == 0

        willpower_trait = await Trait.filter(name="Willpower").first()
        willpower_ct = await CharacterTrait.filter(
            character=character,
            trait=willpower_trait,
        ).first()
        assert willpower_ct is None

    async def test_generate_willpower_value_for_v4_characters(
        self,
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify willpower value is zero when composure and resolve are not set."""
        # Given a character without composure and resolve traits
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER, game_version=GameVersion.V4
        )

        # When generating the willpower value
        await chargen._generate_willpower_value(character)

        # Then verify willpower is in expected range
        willpower_trait = await Trait.filter(name="Willpower").first()
        willpower = await CharacterTrait.filter(
            character=character,
            trait=willpower_trait,
        ).first()
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
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        experience_level: AutoGenExperienceLevel,
        skill_focus: AbilityFocus,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify ability values are generated with correct sum for experience level and skill focus."""
        # Given a character with a specific experience level and skill focus
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            experience_level=experience_level,
            skill_focus=skill_focus,
        )

        # When generating the ability values
        await chargen._generate_ability_values(character)

        # Then verify the sum of ability trait values matches expected distribution
        ability_traits = await _all_traits_in_section("Abilities")
        character_ability_traits = await CharacterTrait.filter(
            character=character,
            trait_id__in=[trait.id for trait in ability_traits],
        )

        sum_of_character_traits = sum([trait.value for trait in character_ability_traits])

        expected_sum = (
            sum(ABILITY_FOCUS_DOT_DISTRIBUTION[skill_focus]) + ABILITY_DOT_BONUS[experience_level]
        )
        assert sum_of_character_traits == expected_sum


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
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        character_class: CharacterClass,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify vampire attributes are not generated for non-vampire characters."""
        # Given a character with a non-vampire class
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER, char_class=character_class
        )

        # When generating the vampire attributes
        await chargen._generate_vampire_attributes(character)

        # Then verify no vampire attributes row was created
        vamp_attrs = await VampireAttributes.filter(character=character).first()
        assert vamp_attrs is None

    async def test_random_vampire_attributes_generated(
        self,
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify vampire attributes are generated for vampire characters."""
        # Given a character with a vampire class
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER, char_class=CharacterClass.VAMPIRE
        )

        # When generating the vampire attributes
        await chargen._generate_vampire_attributes(character)

        # Then verify the vampire attributes are generated
        vampire_clans = list(await VampireClan.filter(is_archived=False))
        vamp_attrs = (
            await VampireAttributes.filter(character=character).select_related("clan").first()
        )
        assert vamp_attrs.clan.name in [x.name for x in vampire_clans]  # type: ignore[union-attr]
        assert vamp_attrs.clan_id in [x.id for x in vampire_clans]  # type: ignore[attr-defined]

        # And verify the disciplines are generated
        all_disciplines = await _all_traits_in_category("Disciplines")
        character_disciplines = await CharacterTrait.filter(
            character=character,
            trait_id__in=[trait.id for trait in all_disciplines],
        )
        character_clan = await VampireClan.filter(id=vamp_attrs.clan_id).first()  # type: ignore[attr-defined]
        await character_clan.fetch_related("disciplines")
        for discipline in character_clan.disciplines:
            assert discipline.id in [ct.trait_id for ct in character_disciplines]  # type: ignore[attr-defined]

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
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        experience_level: AutoGenExperienceLevel,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify extra disciplines are generated for vampire characters."""
        # Given a character with a vampire class
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            char_class=CharacterClass.VAMPIRE,
            experience_level=experience_level,
        )

        # When generating the vampire attributes
        await chargen._generate_vampire_attributes(character)

        # Then verify the extra disciplines are generated
        all_disciplines = await _all_traits_in_category("Disciplines")
        vamp_attrs = await VampireAttributes.filter(character=character).first()
        character_clan = await VampireClan.filter(id=vamp_attrs.clan_id).first()  # type: ignore[attr-defined]
        await character_clan.fetch_related("disciplines")
        clan_discipline_count = len(list(character_clan.disciplines))
        character_disciplines = await CharacterTrait.filter(
            character=character,
            trait_id__in=[trait.id for trait in all_disciplines],
        )
        assert (
            len(character_disciplines)
            == clan_discipline_count + EXTRA_DISCIPLINES_MAP[experience_level]
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
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        clan_name: str,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify the clan is selected correctly."""
        # Given a character with a vampire class
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        vampire_clan = await VampireClan.filter(name=clan_name).first()
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            char_class=CharacterClass.VAMPIRE,
        )
        await chargen._generate_vampire_attributes(character=character, vampire_clan=vampire_clan)

        # Then verify the clan was set correctly
        vamp_attrs = (
            await VampireAttributes.filter(character=character).select_related("clan").first()
        )
        assert vamp_attrs.clan.name == clan_name  # type: ignore[union-attr]


class TestGenerateWerewolfAttributes:
    """Test the generate_werewolf_attributes method."""

    async def test_werewolf_attributes_skipped_for_non_werewolf_characters(
        self,
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify werewolf attributes are not generated for non-werewolf characters."""
        # Given a character with a non-werewolf class
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        for character_class in [
            x for x in list[CharacterClass](CharacterClass) if x != CharacterClass.WEREWOLF
        ]:
            character = await chargen._generate_base_character(
                character_type=CharacterType.PLAYER, char_class=character_class
            )
            await chargen._generate_werewolf_attributes(character)
            ww_attrs = await WerewolfAttributes.filter(character=character).first()
            assert ww_attrs is None

    async def test_random_werewolf_attributes_generated(
        self,
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        debug: Callable[[Any], None],
    ) -> None:
        """Verify werewolf attributes are generated for werewolf characters."""
        # Given a character with a werewolf class
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            char_class=CharacterClass.WEREWOLF,
        )
        await chargen._generate_werewolf_attributes(character)

        werewolf_tribes = list(await WerewolfTribe.filter(is_archived=False))
        werewolf_auspices = list(await WerewolfAuspice.filter(is_archived=False))
        ww_attrs = (
            await WerewolfAttributes.filter(character=character)
            .select_related("tribe", "auspice")
            .first()
        )
        assert ww_attrs.tribe.name in [x.name for x in werewolf_tribes]  # type: ignore[union-attr]
        assert ww_attrs.tribe_id in [x.id for x in werewolf_tribes]  # type: ignore[attr-defined]
        assert ww_attrs.auspice.name in [x.name for x in werewolf_auspices]  # type: ignore[union-attr]
        assert ww_attrs.auspice_id in [x.id for x in werewolf_auspices]  # type: ignore[attr-defined]

        # And verify the tribe and auspice are generated
        auspice = await WerewolfAuspice.filter(id=ww_attrs.auspice_id).first()  # type: ignore[attr-defined]
        assert auspice.name in [x.name for x in werewolf_auspices]

        tribe = await WerewolfTribe.filter(id=ww_attrs.tribe_id).first()  # type: ignore[attr-defined]
        assert tribe.name in [x.name for x in werewolf_tribes]

        # And verify the rage trait is generated
        rage_trait = await Trait.filter(name="Rage").first()
        rage_character_trait = await CharacterTrait.filter(
            character=character,
            trait=rage_trait,
        ).first()
        assert rage_character_trait.value in range(1, 5)

        # And verify the renown traits are generated
        renown_trait_objs = await Trait.filter(name__in=["Honor", "Wisdom", "Glory"])
        renown_traits = await CharacterTrait.filter(
            character=character,
            trait_id__in=[t.id for t in renown_trait_objs],
        )
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
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        tribe_name: str,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify the tribe is selected correctly."""
        # Given a character with a werewolf class
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        werewolf_tribe = await WerewolfTribe.filter(name=tribe_name).first()
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER, char_class=CharacterClass.WEREWOLF
        )
        await chargen._generate_werewolf_attributes(character, werewolf_tribe=werewolf_tribe)

        ww_attrs = (
            await WerewolfAttributes.filter(character=character).select_related("tribe").first()
        )
        assert ww_attrs.tribe.name == tribe_name  # type: ignore[union-attr]
        assert ww_attrs.tribe_id == werewolf_tribe.id  # type: ignore[attr-defined]

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
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        auspice_name: str,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify the auspice is selected correctly."""
        # Given a character with a werewolf class
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        werewolf_auspice = await WerewolfAuspice.filter(name=auspice_name).first()
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER, char_class=CharacterClass.WEREWOLF
        )
        await chargen._generate_werewolf_attributes(character, werewolf_auspice=werewolf_auspice)

        ww_attrs = (
            await WerewolfAttributes.filter(character=character).select_related("auspice").first()
        )
        assert ww_attrs.auspice.name == auspice_name  # type: ignore[union-attr]
        assert ww_attrs.auspice_id == werewolf_auspice.id  # type: ignore[attr-defined]

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
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        debug: Callable[[Any], None],
        auspice_name: str,
        tribe_name: str,
        experience_level: AutoGenExperienceLevel,
    ) -> None:
        """Verify werewolf gifts and rites are generated for werewolf characters."""
        # Given a character
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        werewolf_tribe = await WerewolfTribe.filter(name=tribe_name).first()
        werewolf_auspice = await WerewolfAuspice.filter(name=auspice_name).first()
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            char_class=CharacterClass.WEREWOLF,
            experience_level=experience_level,
        )
        await chargen._generate_werewolf_attributes(
            character, werewolf_tribe=werewolf_tribe, werewolf_auspice=werewolf_auspice
        )
        await chargen._generate_werewolf_gifts_and_rites(character)

        # Gifts and rites are stored as CharacterTrait rows referencing Trait objects
        char_traits = list(
            await CharacterTrait.filter(character=character).prefetch_related("trait")
        )
        gift_trait_ids = {t.id for t in await Trait.filter(gift_renown__isnull=False)}
        rites_category = await TraitCategory.filter(name="Rites").first()
        rite_trait_ids = {t.id for t in await Trait.filter(category_id=rites_category.id)}

        gift_char_traits = [ct for ct in char_traits if ct.trait.id in gift_trait_ids]  # type: ignore[attr-defined]
        rite_char_traits = [ct for ct in char_traits if ct.trait.id in rite_trait_ids]  # type: ignore[attr-defined]

        gift_id_modifiers = EXTRA_WEREWOLF_GIFT_MAP

        assert len(gift_char_traits) == 3 + gift_id_modifiers[experience_level]
        assert len(rite_char_traits) == NUM_WEREWOLF_RITE_MAP[experience_level]


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
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
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
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            experience_level=experience_level,
            char_class=CharacterClass.HUNTER,
        )
        await chargen._generate_hunter_attributes(character)

        # Then verify the hunter attributes are generated
        hunter_attrs = await HunterAttributes.filter(character=character).first()
        assert hunter_attrs.creed in [x.value.title() for x in list(HunterCreed)]

        edges_trait_category = await TraitCategory.filter(name="Edges").first()
        edge_subcategories = list(
            await TraitSubcategory.filter(
                category_id=edges_trait_category.id,
                is_archived=False,
            )
        )

        character_perks = list(
            await CharacterTrait.filter(
                character=character,
                trait__subcategory_id__in=[x.id for x in edge_subcategories],
            ).prefetch_related("trait")
        )

        assert len(character_perks) in expected_num_perks

        total_edges = {perk.trait.subcategory_id for perk in character_perks}  # type: ignore[attr-defined]

        # Perks are randomly sampled from selected edges, so not all edges
        # may be represented in the perks
        assert 1 <= len(total_edges) <= max(expected_num_edges)


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
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        experience_level: AutoGenExperienceLevel,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify advantage values are generated for character."""
        # Given a character
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            experience_level=experience_level,
        )

        # When generating the advantage values
        await chargen._generate_merit_background_values(character)

        # Then verify the advantage values are generated
        backgrounds = await _all_traits_in_category("Backgrounds")
        merits = await _all_traits_in_category("Merits")
        all_traits = backgrounds + merits
        character_traits = await CharacterTrait.filter(
            character=character,
            trait_id__in=[trait.id for trait in all_traits],
        )

        assert (
            sum([trait.value for trait in character_traits])
            == ADVANTAGE_STARTING_DOTS[experience_level]
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
        pg_company_factory: Callable[..., Any],
        pg_user_factory: Callable[..., Any],
        pg_campaign_factory: Callable[..., Any],
        experience_level: AutoGenExperienceLevel,
        debug: Callable[[Any], None],
    ) -> None:
        """Verify flaw values are generated for character."""
        # Given a character
        company = await pg_company_factory()
        user = await pg_user_factory(company=company)
        campaign = await pg_campaign_factory(company=company)
        chargen = CharacterAutogenerationHandler(
            company=company,
            user=user,
            campaign=campaign,
        )
        character = await chargen._generate_base_character(
            character_type=CharacterType.PLAYER,
            experience_level=experience_level,
        )

        # When generating the flaw values
        await chargen._generate_flaw_values(character)

        # Then verify the flaw values are generated
        flaws = await _all_traits_in_category("Flaws")
        character_traits = await CharacterTrait.filter(
            character=character,
            trait_id__in=[trait.id for trait in flaws],
        )
        assert (
            sum([trait.value for trait in character_traits]) == FLAW_STARTING_DOTS[experience_level]
        )
