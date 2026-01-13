"""Integration tests for the bootstrap CLI module."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from vapi.cli.bootstrap import bootstrap, bootstrap_async
from vapi.cli.lib.utils import JSONWithCommentsDecoder
from vapi.constants import PROJECT_ROOT_PATH, WerewolfRenown
from vapi.db.models import (
    AdvantageCategory,
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

pytestmark = pytest.mark.anyio

FIXTURES_PATH = PROJECT_ROOT_PATH / "src/vapi/db/fixtures"


@pytest.fixture
def advantage_categories_fixture() -> list[dict]:
    """Load advantage categories fixture data."""
    fixture_file = FIXTURES_PATH / "advantage_categories.json"
    with fixture_file.open("r") as f:
        return json.load(f, cls=JSONWithCommentsDecoder)


@pytest.fixture
def concepts_fixture() -> list[dict]:
    """Load character concepts fixture data."""
    fixture_file = FIXTURES_PATH / "concepts.json"
    with fixture_file.open("r") as f:
        return json.load(f, cls=JSONWithCommentsDecoder)


@pytest.fixture
def vampire_clans_fixture() -> list[dict]:
    """Load vampire clans fixture data."""
    fixture_file = FIXTURES_PATH / "vampire_clans.json"
    with fixture_file.open("r") as f:
        return json.load(f)


@pytest.fixture
def werewolf_auspices_fixture() -> list[dict]:
    """Load werewolf auspices fixture data."""
    fixture_file = FIXTURES_PATH / "werewolf_auspices.json"
    with fixture_file.open("r") as f:
        return json.load(f)


@pytest.fixture
def werewolf_tribes_fixture() -> list[dict]:
    """Load werewolf tribes fixture data."""
    fixture_file = FIXTURES_PATH / "werewolf_tribes.json"
    with fixture_file.open("r") as f:
        return json.load(f)


@pytest.fixture
def werewolf_gifts_fixture() -> list[dict]:
    """Load werewolf gifts fixture data."""
    fixture_file = FIXTURES_PATH / "werewolf_gifts.json"
    with fixture_file.open("r") as f:
        return json.load(f)


@pytest.fixture
def traits_fixture() -> list[dict]:
    """Load traits fixture data."""
    fixture_file = FIXTURES_PATH / "traits.json"
    with fixture_file.open("r") as f:
        return json.load(f, cls=JSONWithCommentsDecoder)


@pytest.fixture
def werewolf_rites_fixture() -> list[dict]:
    """Load werewolf rites fixture data."""
    fixture_file = FIXTURES_PATH / "werewolf_rites.json"
    with fixture_file.open("r") as f:
        return json.load(f)


@pytest.fixture
def hunter_edges_fixture() -> list[dict]:
    """Load hunter edges fixture data."""
    fixture_file = FIXTURES_PATH / "hunter_edges.json"
    with fixture_file.open("r") as f:
        return json.load(f)


class TestBootstrapAsync:
    """Integration tests for the bootstrap_async function."""

    async def test_bootstrap_creates_all_advantage_categories(
        self, advantage_categories_fixture: list[dict]
    ) -> None:
        """Verify bootstrap creates all advantage categories from fixture."""
        # Given: The fixture data with expected categories
        expected_names = {cat["name"] for cat in advantage_categories_fixture}

        # When: Querying advantage categories from database
        categories = await AdvantageCategory.find().to_list()
        db_names = {c.name for c in categories}

        # Then: All fixture categories should exist in database
        assert expected_names == db_names
        assert len(categories) == len(advantage_categories_fixture)

    async def test_advantage_category_fields_match_fixture(
        self, advantage_categories_fixture: list[dict]
    ) -> None:
        """Verify advantage category fields match fixture data."""
        # Given: The fixture data
        for fixture_cat in advantage_categories_fixture:
            # When: Querying the category from database
            db_cat = await AdvantageCategory.find_one(AdvantageCategory.name == fixture_cat["name"])

            # Then: Fields should match
            assert db_cat is not None, f"Category {fixture_cat['name']} not found in database"
            assert db_cat.description == fixture_cat.get("description")

    async def test_bootstrap_creates_all_character_concepts(
        self, concepts_fixture: list[dict]
    ) -> None:
        """Verify bootstrap creates all character concepts from fixture."""
        # Given: The fixture data with expected concepts
        expected_names = {concept["name"] for concept in concepts_fixture}

        # When: Querying character concepts from database
        concepts = await CharacterConcept.find().to_list()
        db_names = {c.name for c in concepts}

        # Then: All fixture concepts should exist in database
        assert expected_names == db_names
        assert len(concepts) == len(concepts_fixture)

    async def test_character_concept_fields_match_fixture(
        self, concepts_fixture: list[dict]
    ) -> None:
        """Verify character concept fields match fixture data."""
        # Given: Specific concepts from fixture
        for fixture_concept in concepts_fixture[:3]:  # Test first 3 concepts
            # When: Querying the concept from database
            db_concept = await CharacterConcept.find_one(
                CharacterConcept.name == fixture_concept["name"]
            )

            # Then: Fields should match
            assert db_concept is not None
            assert db_concept.description == fixture_concept["description"]
            assert db_concept.max_specialties == fixture_concept["max_specialties"]
            assert len(db_concept.specialties) == len(fixture_concept["specialties"])

    async def test_bootstrap_creates_all_vampire_clans(
        self, vampire_clans_fixture: list[dict]
    ) -> None:
        """Verify bootstrap creates all vampire clans from fixture."""
        # Given: The fixture data with expected clans
        expected_names = {clan["name"] for clan in vampire_clans_fixture}

        # When: Querying vampire clans from database
        clans = await VampireClan.find().to_list()
        db_names = {c.name for c in clans}

        # Then: All fixture clans should exist in database
        assert expected_names == db_names
        assert len(clans) == len(vampire_clans_fixture)

    async def test_vampire_clan_fields_match_fixture(
        self, vampire_clans_fixture: list[dict]
    ) -> None:
        """Verify vampire clan fields match fixture data."""
        # Given: Specific clans from fixture
        for fixture_clan in vampire_clans_fixture:
            # When: Querying the clan from database
            db_clan = await VampireClan.find_one(VampireClan.name == fixture_clan["name"])

            # Then: Fields should match
            assert db_clan is not None, f"Clan {fixture_clan['name']} not found"
            assert db_clan.description == fixture_clan.get("description")
            if fixture_clan.get("link"):
                assert db_clan.link == fixture_clan["link"]

    async def test_vampire_clans_have_correct_disciplines_linked(
        self, vampire_clans_fixture: list[dict]
    ) -> None:
        """Verify vampire clans have correct disciplines linked from fixture."""
        # Given: Clans with disciplines_to_link in fixture
        clans_with_disciplines = [c for c in vampire_clans_fixture if c.get("disciplines_to_link")]

        for fixture_clan in clans_with_disciplines:
            # When: Querying the clan from database
            db_clan = await VampireClan.find_one(VampireClan.name == fixture_clan["name"])
            assert db_clan is not None

            # Then: Number of linked disciplines should match
            expected_discipline_count = len(fixture_clan["disciplines_to_link"])
            assert len(db_clan.discipline_ids) == expected_discipline_count, (
                f"Clan {fixture_clan['name']} has {len(db_clan.discipline_ids)} disciplines, "
                f"expected {expected_discipline_count}"
            )

    async def test_bootstrap_creates_all_werewolf_auspices(
        self, werewolf_auspices_fixture: list[dict]
    ) -> None:
        """Verify bootstrap creates all werewolf auspices from fixture."""
        # Given: The fixture data with expected auspices
        expected_names = {auspice["name"] for auspice in werewolf_auspices_fixture}

        # When: Querying werewolf auspices from database
        auspices = await WerewolfAuspice.find().to_list()
        db_names = {a.name for a in auspices}

        # Then: All fixture auspices should exist in database
        assert expected_names == db_names
        assert len(auspices) == len(werewolf_auspices_fixture)

    async def test_werewolf_auspice_fields_match_fixture(
        self, werewolf_auspices_fixture: list[dict]
    ) -> None:
        """Verify werewolf auspice fields match fixture data."""
        # Given: All auspices from fixture
        for fixture_auspice in werewolf_auspices_fixture:
            # When: Querying the auspice from database
            db_auspice = await WerewolfAuspice.find_one(
                WerewolfAuspice.name == fixture_auspice["name"]
            )

            # Then: Fields should match
            assert db_auspice is not None
            assert db_auspice.link == fixture_auspice.get("link")
            assert db_auspice.name == fixture_auspice["name"]
            assert db_auspice.description == fixture_auspice["description"]

    async def test_bootstrap_creates_all_werewolf_tribes(
        self, werewolf_tribes_fixture: list[dict]
    ) -> None:
        """Verify bootstrap creates all werewolf tribes from fixture."""
        # Given: The fixture data with expected tribes
        expected_names = {tribe["name"] for tribe in werewolf_tribes_fixture}

        # When: Querying werewolf tribes from database
        tribes = await WerewolfTribe.find().to_list()
        db_names = {t.name for t in tribes}

        # Then: All fixture tribes should exist in database
        assert expected_names == db_names
        assert len(tribes) == len(werewolf_tribes_fixture)

    async def test_bootstrap_creates_all_werewolf_rites(
        self, werewolf_rites_fixture: list[dict]
    ) -> None:
        """Verify bootstrap creates all werewolf rites from fixture."""
        # Given: The fixture data with expected rites
        expected_names = {rite["name"] for rite in werewolf_rites_fixture}

        # When: Querying werewolf rites from database
        rites = await WerewolfRite.find().to_list()

        # Then: All fixture rites should exist in database
        assert expected_names == {r.name for r in rites}
        assert len(rites) == len(werewolf_rites_fixture)

    async def test_werewolf_tribe_fields_match_fixture(
        self, werewolf_tribes_fixture: list[dict]
    ) -> None:
        """Verify werewolf tribe fields match fixture data."""
        # Given: All tribes from fixture
        for fixture_tribe in werewolf_tribes_fixture:
            # When: Querying the tribe from database
            db_tribe = await WerewolfTribe.find_one(WerewolfTribe.name == fixture_tribe["name"])

            # Then: Fields should match
            assert db_tribe is not None, f"Tribe {fixture_tribe['name']} not found"
            assert db_tribe.name == fixture_tribe["name"]
            assert db_tribe.description == fixture_tribe["description"]
            assert db_tribe.renown == WerewolfRenown(fixture_tribe["renown"])
            assert db_tribe.patron_spirit == fixture_tribe["patron_spirit"]
            assert db_tribe.favor == fixture_tribe["favor"]
            assert db_tribe.ban == fixture_tribe["ban"]
            assert db_tribe.link == fixture_tribe.get("link")

    async def test_bootstrap_creates_all_hunter_edges(
        self, hunter_edges_fixture: list[dict]
    ) -> None:
        """Verify bootstrap creates all hunter edges from fixture."""
        # Given: The fixture data with expected edges
        expected_names = {edge["name"] for edge in hunter_edges_fixture}

        # When: Querying hunter edges from database
        edges = await HunterEdge.find().to_list()
        db_names = {e.name for e in edges}

        # Then: All fixture edges should exist in database
        assert expected_names == db_names
        assert len(edges) == len(hunter_edges_fixture)

    async def test_bootstrap_creates_all_hunter_edge_perks(
        self, hunter_edges_fixture: list[dict]
    ) -> None:
        """Verify bootstrap creates all hunter edge perks from fixture."""
        # Given: The fixture data with expected perks
        num_perks = 0
        expected_names = set()
        for edge in hunter_edges_fixture:
            for perk in edge["perks"]:
                num_perks += 1
                expected_names.add(perk["name"])

        # When: Querying hunter edge perks from database
        perks = await HunterEdgePerk.find().to_list()
        db_names = {p.name for p in perks}

        # Then: All fixture perks should exist in database
        assert expected_names == db_names
        assert len(perks) == num_perks

    async def test_bootstrap_creates_all_werewolf_gifts(
        self, werewolf_gifts_fixture: list[dict]
    ) -> None:
        """Verify bootstrap creates all werewolf gifts from fixture."""
        # Given: The fixture data with expected gifts
        expected_names = {gift["name"] for gift in werewolf_gifts_fixture}

        # When: Querying werewolf gifts from database
        gifts = await WerewolfGift.find().to_list()
        db_names = {g.name for g in gifts}

        # Then: All fixture gifts should exist in database
        assert expected_names == db_names
        assert len(gifts) == len(werewolf_gifts_fixture)

    async def test_werewolf_gifts_linked_to_tribes_and_auspices(
        self, werewolf_gifts_fixture: list[dict]
    ) -> None:
        """Verify werewolf gifts are linked to tribes and auspices from fixture."""
        # Given: Gifts with tribe_name or auspice_name in fixture
        gifts_with_tribe = [g for g in werewolf_gifts_fixture if g.get("tribe_name")]
        gifts_with_auspice = [g for g in werewolf_gifts_fixture if g.get("auspice_name")]

        # When: Checking database
        gifts = await WerewolfGift.find().to_list()
        gifts_with_tribe_id = [g for g in gifts if g.tribe_id]
        gifts_with_auspice_id = [g for g in gifts if g.auspice_id]

        # Then: Counts should match
        assert len(gifts_with_tribe_id) == len(gifts_with_tribe)
        assert len(gifts_with_auspice_id) == len(gifts_with_auspice)

    async def test_bootstrap_creates_char_sheet_sections(self, traits_fixture: list[dict]) -> None:
        """Verify bootstrap creates all character sheet sections from fixture."""
        # Given: The fixture data with expected sections
        expected_names = {section["name"] for section in traits_fixture}

        # When: Querying sections from database
        sections = await CharSheetSection.find().to_list()
        db_names = {s.name for s in sections}

        # Then: All fixture sections should exist in database
        assert expected_names == db_names
        assert len(sections) == len(traits_fixture)

    async def test_bootstrap_creates_trait_categories(self, traits_fixture: list[dict]) -> None:
        """Verify bootstrap creates all trait categories from fixture."""
        # Given: Count expected categories from fixture
        expected_category_count = sum(
            len(section.get("categories", [])) for section in traits_fixture
        )

        # When: Querying trait categories from database
        categories = await TraitCategory.find().to_list()

        # Then: Count should match
        assert len(categories) == expected_category_count

    async def test_bootstrap_creates_traits(self, traits_fixture: list[dict]) -> None:
        """Verify bootstrap creates all traits from fixture."""
        # Given: Count expected traits from fixture
        expected_trait_count = sum(
            len(cat.get("traits", []))
            for section in traits_fixture
            for cat in section.get("categories", [])
        )

        # When: Querying traits from database (excluding custom traits)
        traits = await Trait.find(Trait.is_custom == False).to_list()

        # Then: Count should match
        assert len(traits) == expected_trait_count

    async def test_bootstrap_is_idempotent(
        self,
        advantage_categories_fixture: list[dict],
        concepts_fixture: list[dict],
        vampire_clans_fixture: list[dict],
        werewolf_auspices_fixture: list[dict],
        werewolf_tribes_fixture: list[dict],
        werewolf_gifts_fixture: list[dict],
        traits_fixture: list[dict],
    ) -> None:
        """Verify running bootstrap multiple times does not duplicate data."""
        # Given: Expected counts from fixtures
        expected_category_count = len(advantage_categories_fixture)
        expected_concept_count = len(concepts_fixture)
        expected_clan_count = len(vampire_clans_fixture)
        expected_auspice_count = len(werewolf_auspices_fixture)
        expected_tribe_count = len(werewolf_tribes_fixture)
        expected_gift_count = len(werewolf_gifts_fixture)
        expected_section_count = len(traits_fixture)

        # When: Running bootstrap again
        await bootstrap_async(do_setup_database=False)

        # Then: Counts should remain the same (no duplicates)
        assert await AdvantageCategory.count() == expected_category_count
        assert await CharacterConcept.count() == expected_concept_count
        assert await VampireClan.count() == expected_clan_count
        assert await WerewolfAuspice.count() == expected_auspice_count
        assert await WerewolfTribe.count() == expected_tribe_count
        assert await WerewolfGift.count() == expected_gift_count
        assert await CharSheetSection.count() == expected_section_count

    async def test_specific_advantage_category_linguistics(
        self, advantage_categories_fixture: list[dict]
    ) -> None:
        """Verify Linguistics advantage category has correct data."""
        # Given: The Linguistics fixture data
        linguistics_fixture = next(
            c for c in advantage_categories_fixture if c["name"] == "Linguistics"
        )

        # When: Querying from database
        db_linguistics = await AdvantageCategory.find_one(AdvantageCategory.name == "Linguistics")

        # Then: All fields should match
        assert db_linguistics is not None
        assert db_linguistics.description == linguistics_fixture["description"]
        assert {c.value for c in db_linguistics.character_classes} == set(
            linguistics_fixture["character_classes"]
        )

    async def test_specific_vampire_clan_brujah(self, vampire_clans_fixture: list[dict]) -> None:
        """Verify Brujah vampire clan has correct data."""
        # Given: The Brujah fixture data
        brujah_fixture = next(c for c in vampire_clans_fixture if c["name"] == "Brujah")

        # When: Querying from database
        db_brujah = await VampireClan.find_one(VampireClan.name == "Brujah")

        # Then: All fields should match
        assert db_brujah is not None
        assert db_brujah.description == brujah_fixture.get("description")
        assert db_brujah.link == brujah_fixture.get("link")
        assert db_brujah.bane is not None
        assert db_brujah.bane.name == brujah_fixture["bane"]["name"]
        assert db_brujah.compulsion is not None
        assert db_brujah.compulsion.name == brujah_fixture["compulsion"]["name"]

    async def test_specific_werewolf_auspice_ahroun(
        self, werewolf_auspices_fixture: list[dict]
    ) -> None:
        """Verify Ahroun werewolf auspice has correct data."""
        # Given: The Ahroun fixture data
        ahroun_fixture = next(a for a in werewolf_auspices_fixture if a["name"] == "Ahroun")

        # When: Querying from database
        db_ahroun = await WerewolfAuspice.find_one(WerewolfAuspice.name == "Ahroun")

        # Then: All fields should match
        assert db_ahroun is not None
        assert db_ahroun.link == ahroun_fixture.get("link")
        assert db_ahroun.name == ahroun_fixture["name"]
        assert db_ahroun.description == ahroun_fixture["description"]

    async def test_specific_werewolf_tribe_silver_fangs(
        self, werewolf_tribes_fixture: list[dict]
    ) -> None:
        """Verify Silver Fangs werewolf tribe has correct data."""
        # Given: The Silver Fangs fixture data
        silver_fangs_fixture = next(
            t for t in werewolf_tribes_fixture if t["name"] == "Silver Fangs"
        )

        # When: Querying from database
        db_silver_fangs = await WerewolfTribe.find_one(WerewolfTribe.name == "Silver Fangs")

        # Then: All fields should match
        assert db_silver_fangs is not None
        assert db_silver_fangs.link == silver_fangs_fixture.get("link")
        assert db_silver_fangs.name == silver_fangs_fixture["name"]
        assert db_silver_fangs.description == silver_fangs_fixture["description"]
        assert db_silver_fangs.renown == WerewolfRenown(silver_fangs_fixture["renown"])
        assert db_silver_fangs.patron_spirit == silver_fangs_fixture["patron_spirit"]
        assert db_silver_fangs.favor == silver_fangs_fixture["favor"]
        assert db_silver_fangs.ban == silver_fangs_fixture["ban"]

    async def test_specific_character_concept_berserker(self, concepts_fixture: list[dict]) -> None:
        """Verify Berserker character concept has correct data."""
        # Given: The BERSERKER fixture data
        berserker_fixture = next(c for c in concepts_fixture if c["name"] == "Berserker")

        # When: Querying from database
        db_berserker = await CharacterConcept.find_one(CharacterConcept.name == "Berserker")

        # Then: All fields should match
        assert db_berserker is not None
        assert db_berserker.description == berserker_fixture["description"]
        assert db_berserker.max_specialties == berserker_fixture["max_specialties"]
        assert len(db_berserker.specialties) == len(berserker_fixture["specialties"])
        assert db_berserker.specialties[0].name == berserker_fixture["specialties"][0]["name"]


class TestBootstrapCommand:
    """Integration tests for the bootstrap click command."""

    def test_bootstrap_command_is_importable(self) -> None:
        """Verify the bootstrap click command can be imported and has correct attributes."""
        # Given: The bootstrap command module

        # When: Inspecting the command
        # Then: Command should have correct attributes
        assert bootstrap.name == "bootstrap"
        assert callable(bootstrap)

    def test_bootstrap_command_has_help_text(self) -> None:
        """Verify the bootstrap click command has help text."""
        # Given: A CLI runner
        runner = CliRunner()

        # When: Running the help command
        result = runner.invoke(bootstrap, ["--help"])

        # Then: Help should display and contain expected text
        assert result.exit_code == 0
        assert "Bootstrap the database" in result.output
