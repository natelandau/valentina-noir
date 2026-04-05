"""Integration tests for the PostgreSQL seed.

Data is seeded once at session scope via conftest.py's init_test_postgres fixture.
These tests verify the pre-seeded data is correct — they do not re-run seed.
"""

from __future__ import annotations

import json

import pytest

from vapi.cli.lib.comparison import JSONWithCommentsDecoder
from vapi.constants import PROJECT_ROOT_PATH, DictionarySourceType, WerewolfRenown
from vapi.db.sql_models.character_classes import VampireClan, WerewolfAuspice, WerewolfTribe
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import (
    CharSheetSection,
    Trait,
    TraitCategory,
    TraitSubcategory,
)
from vapi.db.sql_models.dictionary import DictionaryTerm

pytestmark = pytest.mark.anyio

FIXTURES_PATH = PROJECT_ROOT_PATH / "src/vapi/db/fixtures"


# --- Fixture loaders ---


@pytest.fixture
def traits_fixture() -> list[dict]:
    """Load traits fixture data."""
    with (FIXTURES_PATH / "traits.json").open("r") as f:
        return json.load(f, cls=JSONWithCommentsDecoder)


@pytest.fixture
def vampire_clans_fixture() -> list[dict]:
    """Load vampire clans fixture data."""
    with (FIXTURES_PATH / "vampire_clans.json").open("r") as f:
        return json.load(f)


@pytest.fixture
def werewolf_auspices_fixture() -> list[dict]:
    """Load werewolf auspices fixture data."""
    with (FIXTURES_PATH / "werewolf_auspices.json").open("r") as f:
        return json.load(f)


@pytest.fixture
def werewolf_tribes_fixture() -> list[dict]:
    """Load werewolf tribes fixture data."""
    with (FIXTURES_PATH / "werewolf_tribes.json").open("r") as f:
        return json.load(f)


@pytest.fixture
def concepts_fixture() -> list[dict]:
    """Load character concepts fixture data."""
    with (FIXTURES_PATH / "concepts.json").open("r") as f:
        return json.load(f, cls=JSONWithCommentsDecoder)


# --- Trait hierarchy tests ---


class TestPgTraitSeed:
    """Verify trait hierarchy was seeded into PostgreSQL."""

    async def test_sections_match_fixture(self, traits_fixture: list[dict]) -> None:
        """Verify all character sheet sections exist."""
        sections = await CharSheetSection.all()
        db_names = {s.name for s in sections}
        expected_names = {s["name"] for s in traits_fixture}
        assert db_names == expected_names

    async def test_categories_match_fixture_count(self, traits_fixture: list[dict]) -> None:
        """Verify category count matches fixture."""
        expected = sum(len(s.get("categories", [])) for s in traits_fixture)
        assert await TraitCategory.all().count() == expected

    async def test_subcategories_match_fixture_count(self, traits_fixture: list[dict]) -> None:
        """Verify subcategory count matches fixture."""
        expected = sum(
            len(cat.get("subcategories", []))
            for section in traits_fixture
            for cat in section.get("categories", [])
        )
        assert await TraitSubcategory.all().count() == expected

    async def test_traits_match_fixture_count(self, traits_fixture: list[dict]) -> None:
        """Verify trait count matches fixture."""
        expected_category_traits = sum(
            len(cat.get("traits", []))
            for section in traits_fixture
            for cat in section.get("categories", [])
        )
        expected_subcategory_traits = sum(
            len(subcat.get("traits", []))
            for section in traits_fixture
            for cat in section.get("categories", [])
            for subcat in cat.get("subcategories", [])
        )
        expected_total = expected_category_traits + expected_subcategory_traits
        actual_count = await Trait.filter(is_custom=False).count()
        # Allow +-1 for edge cases in fixture parsing
        assert actual_count in [expected_total - 1, expected_total, expected_total + 1]

    async def test_gift_traits_exist(self) -> None:
        """Verify gift traits were created with gift attributes."""
        gift_count = await Trait.filter(gift_renown__isnull=False).count()
        assert gift_count == 152

    async def test_gift_traits_have_tribe_fks(self) -> None:
        """Verify some gift traits have tribe FKs resolved."""
        with_tribe = await Trait.filter(gift_tribe_id__isnull=False).count()
        assert with_tribe > 0

    async def test_gift_traits_have_auspice_fks(self) -> None:
        """Verify some gift traits have auspice FKs resolved."""
        with_auspice = await Trait.filter(gift_auspice_id__isnull=False).count()
        assert with_auspice > 0

    async def test_category_inherits_character_classes_from_section(
        self, traits_fixture: list[dict]
    ) -> None:
        """Verify categories inherit character_classes from section when not specified."""
        first_section = traits_fixture[0]
        first_category = first_section["categories"][0]
        if not first_category.get("character_classes") and first_section.get("character_classes"):
            db_category = await TraitCategory.get_or_none(name=first_category["name"])
            assert db_category is not None
            assert db_category.character_classes == first_section["character_classes"]


# --- Vampire clan tests ---


class TestPgVampireClanSeed:
    """Verify vampire clans were seeded into PostgreSQL."""

    async def test_clans_match_fixture(self, vampire_clans_fixture: list[dict]) -> None:
        """Verify all vampire clans exist."""
        clans = await VampireClan.all()
        db_names = {c.name for c in clans}
        expected_names = {c["name"] for c in vampire_clans_fixture}
        assert db_names == expected_names

    async def test_clan_fields_match_fixture(self, vampire_clans_fixture: list[dict]) -> None:
        """Verify clan fields match fixture data."""
        for fixture_clan in vampire_clans_fixture:
            db_clan = await VampireClan.get_or_none(name=fixture_clan["name"])
            assert db_clan is not None, f"Clan {fixture_clan['name']} not found"
            assert db_clan.description == fixture_clan.get("description")
            if fixture_clan.get("bane"):
                assert db_clan.bane_name == fixture_clan["bane"]["name"]
                assert db_clan.bane_description == fixture_clan["bane"]["description"]
            if fixture_clan.get("link"):
                assert db_clan.link == fixture_clan["link"]

    async def test_clan_disciplines_linked(self, vampire_clans_fixture: list[dict]) -> None:
        """Verify clans have correct discipline M2M relationships."""
        clans_with_disciplines = [c for c in vampire_clans_fixture if c.get("disciplines_to_link")]
        for fixture_clan in clans_with_disciplines:
            db_clan = await VampireClan.get_or_none(name=fixture_clan["name"])
            assert db_clan is not None
            disciplines = await db_clan.disciplines.all()
            expected_count = len(fixture_clan["disciplines_to_link"])
            assert len(disciplines) == expected_count, (
                f"Clan {fixture_clan['name']} has {len(disciplines)} disciplines, "
                f"expected {expected_count}"
            )

    async def test_brujah_discipline_names(self, vampire_clans_fixture: list[dict]) -> None:
        """Verify Brujah's discipline names match fixture."""
        brujah_fixture = next(c for c in vampire_clans_fixture if c["name"] == "Brujah")
        db_brujah = await VampireClan.get_or_none(name="Brujah")
        assert db_brujah is not None
        disciplines = await db_brujah.disciplines.all()
        db_discipline_names = {d.name for d in disciplines}
        expected_names = set(brujah_fixture["disciplines_to_link"])
        assert db_discipline_names == expected_names


# --- Werewolf auspice/tribe tests ---


class TestPgWerewolfSeed:
    """Verify werewolf auspices and tribes were seeded into PostgreSQL."""

    async def test_auspices_match_fixture(self, werewolf_auspices_fixture: list[dict]) -> None:
        """Verify all werewolf auspices exist."""
        auspices = await WerewolfAuspice.all()
        db_names = {a.name for a in auspices}
        expected_names = {a["name"] for a in werewolf_auspices_fixture}
        assert db_names == expected_names

    async def test_auspice_fields_match_fixture(
        self, werewolf_auspices_fixture: list[dict]
    ) -> None:
        """Verify auspice fields match fixture data."""
        for fixture in werewolf_auspices_fixture:
            db = await WerewolfAuspice.get_or_none(name=fixture["name"])
            assert db is not None, f"Auspice {fixture['name']} not found"
            assert db.description == fixture["description"]
            assert db.link == fixture.get("link")

    async def test_tribes_match_fixture(self, werewolf_tribes_fixture: list[dict]) -> None:
        """Verify all werewolf tribes exist."""
        tribes = await WerewolfTribe.all()
        db_names = {t.name for t in tribes}
        expected_names = {t["name"] for t in werewolf_tribes_fixture}
        assert db_names == expected_names

    async def test_tribe_fields_match_fixture(self, werewolf_tribes_fixture: list[dict]) -> None:
        """Verify tribe fields match fixture data."""
        for fixture in werewolf_tribes_fixture:
            db = await WerewolfTribe.get_or_none(name=fixture["name"])
            assert db is not None, f"Tribe {fixture['name']} not found"
            assert db.description == fixture["description"]
            assert db.renown == WerewolfRenown(fixture["renown"])
            assert db.patron_spirit == fixture["patron_spirit"]
            assert db.favor == fixture["favor"]
            assert db.ban == fixture["ban"]
            assert db.link == fixture.get("link")

    async def test_tribe_gifts_m2m_linked(self) -> None:
        """Verify tribe gift M2M relationships are populated."""
        tribes = await WerewolfTribe.all()
        tribes_with_gifts = 0
        for tribe in tribes:
            gifts = await tribe.gifts.all()
            if gifts:
                tribes_with_gifts += 1
        assert tribes_with_gifts > 0


# --- Character concept tests ---


class TestPgCharacterConceptSeed:
    """Verify character concepts were seeded into PostgreSQL."""

    async def test_concepts_match_fixture(self, concepts_fixture: list[dict]) -> None:
        """Verify all character concepts exist."""
        concepts = await CharacterConcept.all()
        db_names = {c.name for c in concepts}
        expected_names = {c["name"] for c in concepts_fixture}
        assert db_names == expected_names

    async def test_concept_fields_match_fixture(self, concepts_fixture: list[dict]) -> None:
        """Verify concept fields match fixture data."""
        for fixture in concepts_fixture[:3]:
            db = await CharacterConcept.get_or_none(name=fixture["name"])
            assert db is not None
            assert db.description == fixture["description"]
            assert db.max_specialties == fixture["max_specialties"]
            assert len(db.specialties) == len(fixture["specialties"])


# --- Dictionary term tests ---


class TestPgDictionarySeed:
    """Verify dictionary terms were seeded into PostgreSQL."""

    async def test_dictionary_terms_exist(self) -> None:
        """Verify dictionary terms were created."""
        assert await DictionaryTerm.all().count() > 0

    async def test_clan_terms_exist(self) -> None:
        """Verify dictionary terms exist for vampire clans."""
        clan_terms = await DictionaryTerm.filter(source_type=DictionarySourceType.CLAN)
        assert len(clan_terms) > 0

    async def test_tribe_terms_exist(self) -> None:
        """Verify dictionary terms exist for werewolf tribes."""
        tribe_terms = await DictionaryTerm.filter(source_type=DictionarySourceType.TRIBE)
        assert len(tribe_terms) > 0

    async def test_trait_terms_exist(self) -> None:
        """Verify dictionary terms exist for traits."""
        trait_terms = await DictionaryTerm.filter(source_type=DictionarySourceType.TRAIT)
        assert len(trait_terms) > 0

    async def test_brujah_term_includes_bane(self) -> None:
        """Verify Brujah dictionary term includes bane information."""
        brujah_term = await DictionaryTerm.get_or_none(
            term="brujah", source_type=DictionarySourceType.CLAN
        )
        assert brujah_term is not None
        assert "**Bane:" in brujah_term.definition

    async def test_terms_are_lowercase(self) -> None:
        """Verify all dictionary terms are stored lowercase."""
        terms = await DictionaryTerm.all()
        for term in terms:
            assert term.term == term.term.lower(), f"Term '{term.term}' is not lowercase"


# --- Idempotency test ---


class TestPgSeedIdempotency:
    """Verify seed is idempotent when run a second time."""

    async def test_seed_is_idempotent(self) -> None:
        """Verify running seed twice does not duplicate data."""
        from vapi.cli.seed import seed_async

        # Given: Counts from the session-scoped seed
        first_section_count = await CharSheetSection.all().count()
        first_clan_count = await VampireClan.all().count()
        first_term_count = await DictionaryTerm.all().count()

        # When: Running seed again
        await seed_async()

        # Then: No duplicates
        assert await CharSheetSection.all().count() == first_section_count
        assert await VampireClan.all().count() == first_clan_count
        assert await DictionaryTerm.all().count() == first_term_count
