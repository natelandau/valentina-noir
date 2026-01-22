"""Unit tests for the utils module for the CLI."""

from __future__ import annotations

import json
from enum import Enum
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

import click
import pytest
from beanie import PydanticObjectId
from pydantic import BaseModel

from vapi.cli.lib.utils import (
    JSONWithCommentsDecoder,
    SyncCounts,
    TraitSyncResult,
    document_differs_from_fixture,
    get_differing_fields,
    gift_link_to_tribe_and_auspice,
    link_disciplines_to_clan,
    sync_category_traits,
    sync_section_categories,
    sync_single_category,
    sync_single_section,
    sync_single_trait,
)

if TYPE_CHECKING:
    from pytest_mock import MockerFixture

pytestmark = pytest.mark.anyio


class TestSyncCounts:
    """Tests for the SyncCounts dataclass."""

    def test_default_values(self) -> None:
        """Verify SyncCounts initializes with zero counts."""
        # Given: A new SyncCounts instance
        counts = SyncCounts()

        # Then: All values should be zero
        assert counts.created == 0
        assert counts.updated == 0
        assert counts.total == 0

    def test_custom_values(self) -> None:
        """Verify SyncCounts accepts custom values."""
        # Given: Custom values
        counts = SyncCounts(created=5, updated=3, total=10)

        # Then: Values should match
        assert counts.created == 5
        assert counts.updated == 3
        assert counts.total == 10


class TestTraitSyncResult:
    """Tests for the TraitSyncResult dataclass."""

    def test_default_values(self) -> None:
        """Verify TraitSyncResult initializes with default SyncCounts."""
        # Given: A new TraitSyncResult instance
        result = TraitSyncResult()

        # Then: All nested SyncCounts should have zero values
        assert result.sections.created == 0
        assert result.sections.updated == 0
        assert result.sections.total == 0
        assert result.categories.created == 0
        assert result.traits.created == 0

    def test_custom_values(self) -> None:
        """Verify TraitSyncResult accepts custom SyncCounts."""
        # Given: Custom SyncCounts
        sections = SyncCounts(created=1, updated=2, total=3)
        categories = SyncCounts(created=4, updated=5, total=6)
        traits = SyncCounts(created=7, updated=8, total=9)

        # When: Creating TraitSyncResult with custom values
        result = TraitSyncResult(sections=sections, categories=categories, traits=traits)

        # Then: Values should match
        assert result.sections.created == 1
        assert result.categories.total == 6
        assert result.traits.updated == 8


class TestJSONWithCommentsDecoder:
    """Tests for the JSONWithCommentsDecoder class."""

    def test_decode_json_without_comments(self) -> None:
        """Verify decoding standard JSON without comments."""
        # Given: Standard JSON
        json_str = '{"name": "test", "value": 42}'

        # When: Decoding
        result = json.loads(json_str, cls=JSONWithCommentsDecoder)

        # Then: Values should be parsed correctly
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_decode_json_with_single_line_comments(self) -> None:
        """Verify decoding JSON with single-line comments."""
        # Given: JSON with single-line comments
        json_str = """{
            "name": "test", // This is a comment
            "value": 42
        }"""

        # When: Decoding
        result = json.loads(json_str, cls=JSONWithCommentsDecoder)

        # Then: Comments should be stripped
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_decode_json_with_multi_line_comments(self) -> None:
        """Verify decoding JSON with multi-line comments."""
        # Given: JSON with multi-line comments
        json_str = """{
            /* This is a
               multi-line comment */
            "name": "test",
            "value": 42
        }"""

        # When: Decoding
        result = json.loads(json_str, cls=JSONWithCommentsDecoder)

        # Then: Comments should be stripped
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_decode_json_with_mixed_comments(self) -> None:
        """Verify decoding JSON with both comment types."""
        # Given: JSON with both comment types
        json_str = """{
            /* Header comment */
            "name": "test", // inline comment
            "value": 42 /* trailing comment */
        }"""

        # When: Decoding
        result = json.loads(json_str, cls=JSONWithCommentsDecoder)

        # Then: All comments should be stripped
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_decode_preserves_strings_with_slashes(self) -> None:
        """Verify strings containing slashes are preserved."""
        # Given: JSON with strings containing slashes
        json_str = '{"url": "http://example.com/path"}'

        # When: Decoding
        result = json.loads(json_str, cls=JSONWithCommentsDecoder)

        # Then: Strings should be preserved
        assert result["url"] == "http://example.com/path"


class TestDocumentDiffersFromFixture:
    """Tests for the document_differs_from_fixture function."""

    def test_identical_documents(self) -> None:
        """Verify identical documents return False."""
        # Given: A mock document and matching fixture
        document = MagicMock()
        document.name = "Test"
        document.value = 42
        fixture = {"name": "Test", "value": 42}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return False (no difference)
        assert result is False

    def test_differing_string_field(self) -> None:
        """Verify differing string fields return True."""
        # Given: A mock document with different name
        document = MagicMock()
        document.name = "Different"
        document.value = 42
        fixture = {"name": "Test", "value": 42}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return True (difference found)
        assert result is True

    def test_differing_numeric_field(self) -> None:
        """Verify differing numeric fields return True."""
        # Given: A mock document with different value
        document = MagicMock()
        document.name = "Test"
        document.value = 99
        fixture = {"name": "Test", "value": 42}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return True
        assert result is True

    def test_fixture_field_not_in_document(self) -> None:
        """Verify fixture fields not in document are ignored."""
        # Given: A document missing a fixture field
        document = MagicMock(spec=["name"])
        document.name = "Test"
        fixture = {"name": "Test", "missing_field": "value"}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return False (missing fields are skipped)
        assert result is False

    def test_enum_comparison(self) -> None:
        """Verify enum values are compared correctly."""

        # Given: An enum and matching fixture
        class Status(Enum):
            ACTIVE = "active"

        document = MagicMock()
        document.status = Status.ACTIVE
        fixture = {"status": "active"}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return False (enum value matches string)
        assert result is False

    def test_list_comparison(self) -> None:
        """Verify list values are compared correctly."""
        # Given: A document with matching list
        document = MagicMock()
        document.items = ["a", "b", "c"]
        fixture = {"items": ["a", "b", "c"]}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return False
        assert result is False

    def test_list_comparison_different(self) -> None:
        """Verify different lists return True."""
        # Given: A document with different list
        document = MagicMock()
        document.items = ["a", "b", "c"]
        fixture = {"items": ["a", "b", "d"]}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return True
        assert result is True

    def test_pydantic_model_comparison(self) -> None:
        """Verify Pydantic models are compared correctly."""

        # Given: A Pydantic model in the document
        class SubModel(BaseModel):
            field: str

        document = MagicMock()
        document.sub = SubModel(field="value")
        fixture = {"sub": {"field": "value"}}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return False
        assert result is False

    def test_none_comparison(self) -> None:
        """Verify None values are compared correctly."""
        # Given: A document with None value
        document = MagicMock()
        document.optional = None
        fixture = {"optional": None}

        # When: Comparing
        result = document_differs_from_fixture(document, fixture)

        # Then: Should return False
        assert result is False


class TestGetDifferingFields:
    """Tests for the get_differing_fields function."""

    def test_no_differences(self) -> None:
        """Verify no differences returns empty dict."""
        # Given: A matching document and fixture
        document = MagicMock()
        document.name = "Test"
        document.value = 42
        fixture = {"name": "Test", "value": 42}

        # When: Getting differences
        result = get_differing_fields(document, fixture)

        # Then: Should return empty dict
        assert result == {}

    def test_single_difference(self) -> None:
        """Verify single difference is returned correctly."""
        # Given: A document with one different field
        document = MagicMock()
        document.name = "Different"
        document.value = 42
        fixture = {"name": "Test", "value": 42}

        # When: Getting differences
        result = get_differing_fields(document, fixture)

        # Then: Should contain only the differing field
        assert len(result) == 1
        assert "name" in result
        assert result["name"] == ("Different", "Test")

    def test_multiple_differences(self) -> None:
        """Verify multiple differences are returned correctly."""
        # Given: A document with multiple different fields
        document = MagicMock()
        document.name = "Different"
        document.value = 99
        fixture = {"name": "Test", "value": 42}

        # When: Getting differences
        result = get_differing_fields(document, fixture)

        # Then: Should contain all differing fields
        assert len(result) == 2
        assert result["name"] == ("Different", "Test")
        assert result["value"] == (99, 42)

    def test_missing_document_field(self) -> None:
        """Verify missing document fields are skipped."""
        # Given: A document missing a fixture field
        document = MagicMock(spec=["name"])
        document.name = "Test"
        fixture = {"name": "Test", "missing_field": "value"}

        # When: Getting differences
        result = get_differing_fields(document, fixture)

        # Then: Missing field should not appear in differences
        assert "missing_field" not in result
        assert result == {}

    def test_enum_difference(self) -> None:
        """Verify enum differences are normalized."""

        # Given: An enum with different value
        class Status(Enum):
            ACTIVE = "active"

        document = MagicMock()
        document.status = Status.ACTIVE
        fixture = {"status": "inactive"}

        # When: Getting differences
        result = get_differing_fields(document, fixture)

        # Then: Should show normalized enum value
        assert result["status"] == ("active", "inactive")


class TestLinkDisciplinesToClan:
    """Tests for the link_disciplines_to_clan function."""

    async def test_no_disciplines_to_link(self, mocker: MockerFixture) -> None:
        """Verify returns False when no disciplines to link."""
        # Given: A clan with no disciplines
        clan = MagicMock()
        clan.discipline_ids = []
        fixture_clan: dict[str, Any] = {}

        # When: Linking disciplines
        result = await link_disciplines_to_clan(clan, fixture_clan)

        # Then: Should return False
        assert result is False

    async def test_links_new_discipline(self, mocker: MockerFixture) -> None:
        """Verify linking a new discipline to a clan."""
        # Given: A clan and a discipline to link
        discipline_id = PydanticObjectId()
        discipline = MagicMock()
        discipline.id = discipline_id
        discipline.name = "Dominate"

        clan = MagicMock()
        clan.discipline_ids = []
        clan.save = AsyncMock()

        fixture_clan = {"disciplines_to_link": ["Dominate"]}

        mock_trait = mocker.patch("vapi.cli.lib.utils.Trait")
        mock_trait.find_one = AsyncMock(return_value=discipline)

        # When: Linking disciplines
        result = await link_disciplines_to_clan(clan, fixture_clan)

        # Then: Should return True and add discipline
        assert result is True
        assert discipline_id in clan.discipline_ids
        clan.save.assert_called()

    async def test_removes_unlisted_discipline(self, mocker: MockerFixture) -> None:
        """Verify removing a discipline not in fixture."""
        # Given: A clan with a discipline not in fixture
        discipline_id = PydanticObjectId()
        discipline = MagicMock()
        discipline.id = discipline_id
        discipline.name = "OldDiscipline"

        clan = MagicMock()
        clan.discipline_ids = [discipline_id]
        clan.save = AsyncMock()

        fixture_clan = {"disciplines_to_link": []}

        mock_trait = mocker.patch("vapi.cli.lib.utils.Trait")
        mock_trait.find_one = AsyncMock(return_value=discipline)

        # When: Linking disciplines
        result = await link_disciplines_to_clan(clan, fixture_clan)

        # Then: Should return True and remove discipline
        assert result is True
        assert discipline_id not in clan.discipline_ids

    async def test_raises_on_missing_discipline(self, mocker: MockerFixture) -> None:
        """Verify raises Abort when discipline not found."""
        # Given: A clan with a non-existent discipline ID
        discipline_id = PydanticObjectId()
        clan = MagicMock()
        clan.discipline_ids = [discipline_id]

        fixture_clan: dict[str, Any] = {}

        mock_trait = mocker.patch("vapi.cli.lib.utils.Trait")
        mock_trait.find_one = AsyncMock(return_value=None)

        # When/Then: Should raise click.Abort
        with pytest.raises(click.Abort):
            await link_disciplines_to_clan(clan, fixture_clan)


class TestGiftLinkToTribeAndAuspice:
    """Tests for the gift_link_to_tribe_and_auspice function."""

    async def test_no_tribe_or_auspice(self) -> None:
        """Verify returns False when no tribe or auspice in fixture."""
        # Given: A gift and fixture without tribe/auspice
        gift = MagicMock()
        fixture_gift: dict[str, Any] = {}
        tribes: list[Any] = []
        auspices: list[Any] = []

        # When: Linking
        result = await gift_link_to_tribe_and_auspice(gift, fixture_gift, tribes, auspices)

        # Then: Should return False
        assert result is False

    async def test_links_gift_to_tribe(self) -> None:
        """Verify linking a gift to a tribe."""
        # Given: A gift and tribe to link
        tribe_id = PydanticObjectId()
        gift_id = PydanticObjectId()

        tribe = MagicMock()
        tribe.id = tribe_id
        tribe.name = "Silver Fangs"
        tribe.gift_ids = []
        tribe.save = AsyncMock()

        gift = MagicMock()
        gift.id = gift_id
        gift.tribe_id = None
        gift.auspice_id = None
        gift.save = AsyncMock()

        fixture_gift = {"tribe_name": "Silver Fangs"}
        tribes = [tribe]
        auspices: list[Any] = []

        # When: Linking
        result = await gift_link_to_tribe_and_auspice(gift, fixture_gift, tribes, auspices)

        # Then: Should return True and link gift to tribe
        assert result is True
        assert gift.tribe_id == tribe_id
        assert gift_id in tribe.gift_ids
        tribe.save.assert_called()
        gift.save.assert_called()

    async def test_links_gift_to_auspice(self) -> None:
        """Verify linking a gift to an auspice."""
        # Given: A gift and auspice to link
        auspice_id = PydanticObjectId()
        gift_id = PydanticObjectId()

        auspice = MagicMock()
        auspice.id = auspice_id
        auspice.name = "Ahroun"
        auspice.gift_ids = []
        auspice.save = AsyncMock()

        gift = MagicMock()
        gift.id = gift_id
        gift.tribe_id = None
        gift.auspice_id = None
        gift.save = AsyncMock()

        fixture_gift = {"auspice_name": "Ahroun"}
        tribes: list[Any] = []
        auspices = [auspice]

        # When: Linking
        result = await gift_link_to_tribe_and_auspice(gift, fixture_gift, tribes, auspices)

        # Then: Should return True and link gift to auspice
        assert result is True
        assert gift.auspice_id == auspice_id
        assert gift_id in auspice.gift_ids

    async def test_raises_on_missing_tribe(self) -> None:
        """Verify raises Abort when tribe not found."""
        # Given: A fixture with non-existent tribe
        gift = MagicMock()
        gift.tribe_id = None
        gift.auspice_id = None

        fixture_gift = {"tribe_name": "NonExistent"}
        tribes: list[Any] = []
        auspices: list[Any] = []

        # When/Then: Should raise click.Abort
        with pytest.raises(click.Abort):
            await gift_link_to_tribe_and_auspice(gift, fixture_gift, tribes, auspices)

    async def test_raises_on_missing_auspice(self) -> None:
        """Verify raises Abort when auspice not found."""
        # Given: A fixture with non-existent auspice
        gift = MagicMock()
        gift.tribe_id = None
        gift.auspice_id = None

        fixture_gift = {"auspice_name": "NonExistent"}
        tribes: list[Any] = []
        auspices: list[Any] = []

        # When/Then: Should raise click.Abort
        with pytest.raises(click.Abort):
            await gift_link_to_tribe_and_auspice(gift, fixture_gift, tribes, auspices)

    async def test_removes_old_tribe_link(self, mocker: MockerFixture) -> None:
        """Verify removing old tribe link when changing tribes."""
        # Given: A gift linked to old tribe, being linked to new tribe
        old_tribe_id = PydanticObjectId()
        new_tribe_id = PydanticObjectId()
        gift_id = PydanticObjectId()

        old_tribe = MagicMock()
        old_tribe.id = old_tribe_id
        old_tribe.gift_ids = [gift_id]
        old_tribe.save = AsyncMock()

        new_tribe = MagicMock()
        new_tribe.id = new_tribe_id
        new_tribe.name = "New Tribe"
        new_tribe.gift_ids = []
        new_tribe.save = AsyncMock()

        gift = MagicMock()
        gift.id = gift_id
        gift.tribe_id = old_tribe_id
        gift.auspice_id = None
        gift.save = AsyncMock()

        mock_werewolf_tribe = mocker.patch("vapi.cli.lib.utils.WerewolfTribe")
        mock_werewolf_tribe.find_one = AsyncMock(return_value=old_tribe)

        fixture_gift = {"tribe_name": "New Tribe"}
        tribes = [new_tribe]
        auspices: list[Any] = []

        # When: Linking
        result = await gift_link_to_tribe_and_auspice(gift, fixture_gift, tribes, auspices)

        # Then: Should return True and update links
        assert result is True
        assert gift_id not in old_tribe.gift_ids
        assert gift_id in new_tribe.gift_ids


class TestSyncSingleSection:
    """Tests for the sync_single_section function."""

    async def test_creates_new_section(self, mocker: MockerFixture) -> None:
        """Verify creating a new section when not found."""
        # Given: A fixture section not in database
        fixture_section = {
            "name": "Physical",
            "description": "Physical attributes",
            "order": 1,
        }

        mock_section_class = mocker.patch("vapi.cli.lib.utils.CharSheetSection")
        mock_section_class.find_one = AsyncMock(return_value=None)
        mock_section_instance = MagicMock()
        mock_section_instance.save = AsyncMock()
        mock_section_class.return_value = mock_section_instance

        # When: Syncing
        _, created, updated = await sync_single_section(fixture_section)

        # Then: Should create new section
        assert created is True
        assert updated is False
        mock_section_instance.save.assert_called_once()

    async def test_updates_existing_section(self, mocker: MockerFixture) -> None:
        """Verify updating an existing section with differences."""
        # Given: An existing section with different values
        fixture_section = {
            "name": "Physical",
            "description": "Updated description",
            "order": 1,
        }

        existing_section = MagicMock()
        existing_section.name = "Physical"
        existing_section.description = "Old description"
        existing_section.order = 1
        existing_section.save = AsyncMock()

        mock_section_class = mocker.patch("vapi.cli.lib.utils.CharSheetSection")
        mock_section_class.find_one = AsyncMock(return_value=existing_section)

        mocker.patch("vapi.cli.lib.utils.document_differs_from_fixture", return_value=True)
        mocker.patch(
            "vapi.cli.lib.utils.get_differing_fields",
            return_value={"description": ("Old description", "Updated description")},
        )

        # When: Syncing
        _, created, updated = await sync_single_section(fixture_section)

        # Then: Should update existing section
        assert created is False
        assert updated is True
        existing_section.save.assert_called_once()

    async def test_no_update_when_identical(self, mocker: MockerFixture) -> None:
        """Verify no update when section matches fixture."""
        # Given: An existing section matching fixture
        fixture_section = {
            "name": "Physical",
            "description": "Description",
            "order": 1,
        }

        existing_section = MagicMock()
        existing_section.name = "Physical"
        existing_section.description = "Description"
        existing_section.order = 1

        mock_section_class = mocker.patch("vapi.cli.lib.utils.CharSheetSection")
        mock_section_class.find_one = AsyncMock(return_value=existing_section)

        mocker.patch("vapi.cli.lib.utils.document_differs_from_fixture", return_value=False)

        # When: Syncing
        _, created, updated = await sync_single_section(fixture_section)

        # Then: Should not create or update
        assert created is False
        assert updated is False


class TestSyncSingleCategory:
    """Tests for the sync_single_category function."""

    async def test_creates_new_category(self, mocker: MockerFixture) -> None:
        """Verify creating a new category when not found."""
        # Given: A fixture category not in database
        fixture_category = {
            "name": "Strength",
            "description": "Physical strength",
            "order": 1,
        }

        section = MagicMock()
        section.id = PydanticObjectId()

        mock_category_class = mocker.patch("vapi.cli.lib.utils.TraitCategory")
        mock_category_class.find_one = AsyncMock(return_value=None)
        mock_category_instance = MagicMock()
        mock_category_instance.save = AsyncMock()
        mock_category_class.return_value = mock_category_instance

        # When: Syncing
        _, created, updated = await sync_single_category(fixture_category, section)

        # Then: Should create new category
        assert created is True
        assert updated is False
        mock_category_instance.save.assert_called_once()

    async def test_updates_existing_category(self, mocker: MockerFixture) -> None:
        """Verify updating an existing category with differences."""
        # Given: An existing category with different values
        fixture_category = {
            "name": "Strength",
            "description": "Updated description",
            "order": 2,
        }

        section = MagicMock()
        section.id = PydanticObjectId()

        existing_category = MagicMock()
        existing_category.name = "Strength"
        existing_category.description = "Old description"
        existing_category.order = 1
        existing_category.save = AsyncMock()

        mock_category_class = mocker.patch("vapi.cli.lib.utils.TraitCategory")
        mock_category_class.find_one = AsyncMock(return_value=existing_category)

        mocker.patch("vapi.cli.lib.utils.document_differs_from_fixture", return_value=True)
        mocker.patch(
            "vapi.cli.lib.utils.get_differing_fields",
            return_value={"description": ("Old description", "Updated description")},
        )

        # When: Syncing
        _, created, updated = await sync_single_category(fixture_category, section)

        # Then: Should update existing category
        assert created is False
        assert updated is True
        existing_category.save.assert_called_once()


class TestSyncSingleTrait:
    """Tests for the sync_single_trait function."""

    async def test_creates_new_trait(self, mocker: MockerFixture) -> None:
        """Verify creating a new trait when not found."""
        # Given: A fixture trait not in database
        fixture_trait = {
            "name": "Strength",
            "description": "Physical power",
        }
        fixture_category = {
            "name": "Attributes",
            "initial_cost": 3,
            "upgrade_cost": 5,
        }

        category = MagicMock()
        category.id = PydanticObjectId()

        mock_trait_class = mocker.patch("vapi.cli.lib.utils.Trait")
        mock_trait_class.find_one = AsyncMock(return_value=None)

        mock_trait_instance = MagicMock()
        mock_trait_instance.save = AsyncMock()
        mock_trait_instance.advantage_category_name = None
        mock_trait_class.return_value = mock_trait_instance

        category.save = AsyncMock()

        # When: Syncing
        _, created, updated = await sync_single_trait(fixture_trait, fixture_category, category)

        # Then: Should create new trait with default costs
        assert created is True
        assert updated is False
        mock_trait_instance.save.assert_called_once()
        assert mock_trait_instance.initial_cost == 3
        assert mock_trait_instance.upgrade_cost == 5

    async def test_updates_existing_trait(self, mocker: MockerFixture) -> None:
        """Verify updating an existing trait with differences."""
        # Given: An existing trait with different values
        fixture_trait = {
            "name": "Strength",
            "description": "Updated description",
        }
        fixture_category = {"name": "Attributes"}

        category = MagicMock()
        category.id = PydanticObjectId()
        category.save = AsyncMock()

        existing_trait = MagicMock()
        existing_trait.name = "Strength"
        existing_trait.description = "Old description"
        existing_trait.save = AsyncMock()

        mock_trait_class = mocker.patch("vapi.cli.lib.utils.Trait")
        mock_trait_class.find_one = AsyncMock(return_value=existing_trait)

        mocker.patch("vapi.cli.lib.utils.document_differs_from_fixture", return_value=True)
        mocker.patch(
            "vapi.cli.lib.utils.get_differing_fields",
            return_value={"description": ("Old description", "Updated description")},
        )

        # When: Syncing
        _, created, updated = await sync_single_trait(fixture_trait, fixture_category, category)

        # Then: Should update existing trait
        assert created is False
        assert updated is True
        existing_trait.save.assert_called_once()

    async def test_links_to_advantage_category(self, mocker: MockerFixture) -> None:
        """Verify linking trait to advantage category."""
        # Given: A new trait with advantage_category_name
        fixture_trait = {
            "name": "Retainer",
            "description": "A loyal servant",
        }
        fixture_category = {"name": "Backgrounds"}

        category = MagicMock()
        category.id = PydanticObjectId()
        category.save = AsyncMock()

        advantage_category = MagicMock()
        advantage_category.id = PydanticObjectId()

        mock_trait_class = mocker.patch("vapi.cli.lib.utils.Trait")
        mock_trait_class.find_one = AsyncMock(return_value=None)

        mock_trait_instance = MagicMock()
        mock_trait_instance.advantage_category_name = "Allies"
        mock_trait_instance.save = AsyncMock()
        mock_trait_class.return_value = mock_trait_instance

        mock_advantage_class = mocker.patch("vapi.cli.lib.utils.AdvantageCategory")
        mock_advantage_class.find_one = AsyncMock(return_value=advantage_category)

        # When: Syncing
        await sync_single_trait(fixture_trait, fixture_category, category)

        # Then: Should link to advantage category
        assert mock_trait_instance.advantage_category_id == advantage_category.id


class TestSyncCategoryTraits:
    """Tests for the sync_category_traits function."""

    async def test_syncs_multiple_traits(self, mocker: MockerFixture) -> None:
        """Verify syncing multiple traits within a category."""
        # Given: A category with multiple traits
        fixture_category = {
            "name": "Attributes",
            "traits": [
                {"name": "Strength"},
                {"name": "Dexterity"},
                {"name": "Stamina"},
            ],
        }

        category = MagicMock()
        category.id = PydanticObjectId()

        mock_sync_single = mocker.patch("vapi.cli.lib.utils.sync_single_trait")
        mock_sync_single.side_effect = [
            (MagicMock(), True, False),  # created
            (MagicMock(), False, True),  # updated
            (MagicMock(), False, False),  # unchanged
        ]

        # When: Syncing
        counts = await sync_category_traits(fixture_category, category)

        # Then: Should return correct counts
        assert counts.total == 3
        assert counts.created == 1
        assert counts.updated == 1

    async def test_empty_traits_list(self) -> None:
        """Verify handling category with no traits."""
        # Given: A category with no traits
        fixture_category = {"name": "Empty", "traits": []}

        category = MagicMock()

        # When: Syncing
        counts = await sync_category_traits(fixture_category, category)

        # Then: Should return zero counts
        assert counts.total == 0
        assert counts.created == 0
        assert counts.updated == 0


class TestSyncSectionCategories:
    """Tests for the sync_section_categories function."""

    async def test_syncs_categories_and_traits(self, mocker: MockerFixture) -> None:
        """Verify syncing categories and their traits within a section."""
        # Given: A section with categories and traits
        fixture_section = {
            "name": "Physical",
            "categories": [
                {
                    "name": "Attributes",
                    "traits": [{"name": "Strength"}, {"name": "Dexterity"}],
                },
                {
                    "name": "Skills",
                    "traits": [{"name": "Athletics"}],
                },
            ],
        }

        section = MagicMock()
        section.id = PydanticObjectId()

        mock_category = MagicMock()
        mock_category.id = PydanticObjectId()

        mock_sync_category = mocker.patch("vapi.cli.lib.utils.sync_single_category")
        mock_sync_category.side_effect = [
            (mock_category, True, False),  # first category created
            (mock_category, False, True),  # second category updated
        ]

        mock_sync_traits = mocker.patch("vapi.cli.lib.utils.sync_category_traits")
        mock_sync_traits.side_effect = [
            SyncCounts(created=2, updated=0, total=2),
            SyncCounts(created=1, updated=0, total=1),
        ]

        # When: Syncing
        category_counts, trait_counts = await sync_section_categories(fixture_section, section)

        # Then: Should return correct counts
        assert category_counts.total == 2
        assert category_counts.created == 1
        assert category_counts.updated == 1
        assert trait_counts.total == 3
        assert trait_counts.created == 3

    async def test_empty_categories_list(self) -> None:
        """Verify handling section with no categories."""
        # Given: A section with no categories
        fixture_section = {"name": "Empty", "categories": []}

        section = MagicMock()

        # When: Syncing
        category_counts, trait_counts = await sync_section_categories(fixture_section, section)

        # Then: Should return zero counts
        assert category_counts.total == 0
        assert trait_counts.total == 0
