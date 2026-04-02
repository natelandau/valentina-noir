"""Fixtures for Tortoise ORM models.

Parallel to fixture_models.py (Beanie-based) during the migration. Once all domains
are migrated (Session 11), delete fixture_models.py and consolidate into this file.

Fixtures that create constant data (traits, concepts, etc.) must clean up after
themselves because the cleanup_pg_database fixture only deletes non-constant tables.
"""

from __future__ import annotations

import contextlib
from typing import Any

import pytest

from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.character import (
    Character,
    CharacterInventory,
    CharacterTrait,
    Specialty,
    VampireAttributes,
    WerewolfAttributes,
)
from vapi.db.sql_models.character_concept import CharacterConcept
from vapi.db.sql_models.character_sheet import CharSheetSection, Trait, TraitCategory
from vapi.db.sql_models.company import Company, CompanySettings
from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.db.sql_models.dictionary import DictionaryTerm
from vapi.db.sql_models.user import CampaignExperience, User

pytestmark = pytest.mark.anyio


@pytest.fixture
async def pg_company_factory():
    """Return a factory that creates Tortoise Company instances with cleanup.

    Company is non-constant data, so the per-test cleanup handles deletion.
    The factory still tracks instances for explicit cleanup in case it is used
    in tests that do not rely on the automatic cleanup fixture.
    """
    created: list[Company] = []

    async def _factory(**kwargs: Any) -> Company:
        defaults: dict[str, Any] = {
            "name": "Test Company",
            "email": "test@example.com",
        }
        defaults.update(kwargs)
        company = await Company.create(**defaults)
        # Re-fetch from DB so Tortoise normalizes the UUID to stdlib uuid.UUID,
        # avoiding type-mismatch issues when comparing with term.company_id
        company = await Company.get(id=str(company.id))
        # Auto-create CompanySettings so services that query settings don't fail
        await CompanySettings.get_or_create(company=company)
        created.append(company)
        return company

    yield _factory

    for company in created:
        with contextlib.suppress(Exception):
            await company.delete()


@pytest.fixture
async def pg_trait_factory():
    """Return a factory that creates Tortoise Trait instances and cleans up after the test.

    Traits are constant data preserved across tests, so the factory tracks
    created instances and deletes them when the test completes.
    """
    created: list[Trait] = []

    async def _factory(**kwargs: Any) -> Trait:
        if "category" not in kwargs and "category_id" not in kwargs:
            category = await TraitCategory.filter(is_archived=False).first()
            kwargs["category"] = category
        if "sheet_section" not in kwargs and "sheet_section_id" not in kwargs:
            category = kwargs.get("category") or await TraitCategory.get(id=kwargs["category_id"])
            section = await CharSheetSection.get(id=category.sheet_section_id)
            kwargs["sheet_section"] = section

        defaults: dict[str, Any] = {
            "name": "Test Trait",
            "min_value": 0,
            "max_value": 5,
            "show_when_zero": True,
            "initial_cost": 1,
            "upgrade_cost": 2,
            "is_custom": False,
            "custom_for_character_id": None,
            "is_archived": False,
        }
        defaults.update(kwargs)
        trait = await Trait.create(**defaults)
        created.append(trait)
        return trait

    yield _factory

    for trait in created:
        await trait.delete()


@pytest.fixture
async def pg_character_concept_factory():
    """Return a factory that creates Tortoise CharacterConcept instances with cleanup.

    Concepts are constant data preserved across tests, so the factory tracks
    created instances and deletes them when the test completes.
    """
    created: list[CharacterConcept] = []

    async def _factory(**kwargs: Any) -> CharacterConcept:
        defaults: dict[str, Any] = {
            "name": "Test Concept",
            "description": "Test description",
            "examples": ["Example 1", "Example 2"],
            "company_id": None,
            "is_archived": False,
        }
        defaults.update(kwargs)
        concept = await CharacterConcept.create(**defaults)
        created.append(concept)
        return concept

    yield _factory

    for concept in created:
        await concept.delete()


@pytest.fixture
async def pg_developer_factory():
    """Return a factory that creates Tortoise Developer instances with cleanup.

    Developer is non-constant data, so the per-test cleanup handles deletion.
    The factory still tracks instances for explicit cleanup in case it is used
    in tests that do not rely on the automatic cleanup fixture.
    """
    created: list[Developer] = []

    async def _factory(**kwargs: Any) -> Developer:
        defaults: dict[str, Any] = {
            "username": f"test-dev-{len(created)}",
            "email": f"dev{len(created)}@example.com",
            "is_global_admin": False,
        }
        defaults.update(kwargs)
        developer = await Developer.create(**defaults)
        # Re-fetch from DB so Tortoise normalizes the UUID to stdlib uuid.UUID,
        # avoiding type-mismatch issues when comparing with developer.id
        developer = await Developer.get(id=str(developer.id))
        created.append(developer)
        return developer

    yield _factory

    for developer in created:
        with contextlib.suppress(Exception):
            await developer.delete()


@pytest.fixture
async def pg_developer_company_permission_factory():
    """Return a factory that creates Tortoise DeveloperCompanyPermission instances with cleanup.

    Permissions are non-constant data. Caller must supply developer, company, and permission.
    """
    created: list[DeveloperCompanyPermission] = []

    async def _factory(**kwargs: Any) -> DeveloperCompanyPermission:
        permission = await DeveloperCompanyPermission.create(**kwargs)
        created.append(permission)
        return permission

    yield _factory

    for permission in created:
        with contextlib.suppress(Exception):
            await permission.delete()


@pytest.fixture
async def pg_dictionary_term_factory():
    """Return a factory that creates Tortoise DictionaryTerm instances with cleanup.

    Dictionary terms include bootstrap-seeded data, so the factory tracks
    created instances and deletes them when the test completes.
    """
    created: list[DictionaryTerm] = []

    async def _factory(**kwargs: Any) -> DictionaryTerm:
        defaults: dict[str, Any] = {
            "term": "Test Term",
            "definition": "Test definition",
            "link": "https://example.com/test",
            "synonyms": ["test synonym", "test synonym 2"],
            "company_id": None,
            "source_type": None,
            "source_id": None,
            "is_archived": False,
        }
        defaults.update(kwargs)
        # Tortoise's UUIDField cannot accept uuid_utils.UUID directly; convert via str
        for uuid_field in ("company_id", "source_id"):
            if defaults.get(uuid_field) is not None:
                defaults[uuid_field] = str(defaults[uuid_field])
        term = await DictionaryTerm.create(**defaults)
        created.append(term)
        return term

    yield _factory

    for term in created:
        await term.delete()


@pytest.fixture
async def pg_user_factory():
    """Return a factory that creates Tortoise User instances.

    User is non-constant data, so the per-test cleanup handles deletion.
    """
    created: list[User] = []
    _counter = 0

    async def _factory(**kwargs: Any) -> User:
        nonlocal _counter
        _counter += 1
        defaults: dict[str, Any] = {
            "username": f"test-user-{_counter}",
            "email": f"user{_counter}@example.com",
            "role": "PLAYER",
        }
        defaults.update(kwargs)
        user = await User.create(**defaults)
        user = await User.filter(id=user.id).prefetch_related("campaign_experiences").first()
        created.append(user)
        return user

    yield _factory

    for user in created:
        with contextlib.suppress(Exception):
            await user.delete()


@pytest.fixture
async def pg_campaign_factory():
    """Return a factory that creates Tortoise Campaign instances.

    Campaign is non-constant data, so the per-test cleanup handles deletion.
    """
    created: list[Campaign] = []
    _counter = 0

    async def _factory(**kwargs: Any) -> Campaign:
        nonlocal _counter
        _counter += 1
        defaults: dict[str, Any] = {
            "name": f"Test Campaign {_counter}",
        }
        defaults.update(kwargs)
        campaign = await Campaign.create(**defaults)
        # Re-fetch from DB so Tortoise normalizes the UUID to stdlib uuid.UUID,
        # avoiding type-mismatch issues when comparing with campaign.id
        campaign = await Campaign.get(id=str(campaign.id))
        created.append(campaign)
        return campaign

    yield _factory

    for campaign in created:
        with contextlib.suppress(Exception):
            await campaign.delete()


@pytest.fixture
async def pg_campaign_experience_factory():
    """Return a factory that creates Tortoise CampaignExperience instances.

    CampaignExperience is non-constant data, so the per-test cleanup handles deletion.
    Caller must supply user and campaign (or user_id and campaign_id).
    """
    created: list[CampaignExperience] = []

    async def _factory(**kwargs: Any) -> CampaignExperience:
        experience = await CampaignExperience.create(**kwargs)
        created.append(experience)
        return experience

    yield _factory

    for experience in created:
        with contextlib.suppress(Exception):
            await experience.delete()


@pytest.fixture
async def pg_campaign_book_factory():
    """Return a factory that creates Tortoise CampaignBook instances.

    CampaignBook is non-constant data, so the per-test cleanup handles deletion.
    Auto-assigns number by counting active siblings + 1.
    """
    created: list[CampaignBook] = []
    _counter = 0

    async def _factory(**kwargs: Any) -> CampaignBook:
        nonlocal _counter
        _counter += 1
        campaign_id = kwargs.get("campaign_id") or kwargs.get("campaign")
        if campaign_id and hasattr(campaign_id, "id"):
            campaign_id = campaign_id.id

        if "number" not in kwargs and campaign_id:
            count = await CampaignBook.filter(campaign_id=campaign_id, is_archived=False).count()
            kwargs["number"] = count + 1
        elif "number" not in kwargs:
            kwargs["number"] = _counter

        defaults: dict[str, Any] = {
            "name": f"Test Book {_counter}",
        }
        defaults.update(kwargs)
        book = await CampaignBook.create(**defaults)
        book = await CampaignBook.get(id=str(book.id))
        created.append(book)
        return book

    yield _factory

    for book in created:
        with contextlib.suppress(Exception):
            await book.delete()


@pytest.fixture
async def pg_campaign_chapter_factory():
    """Return a factory that creates Tortoise CampaignChapter instances.

    CampaignChapter is non-constant data, so the per-test cleanup handles deletion.
    Auto-assigns number by counting active siblings + 1.
    """
    created: list[CampaignChapter] = []
    _counter = 0

    async def _factory(**kwargs: Any) -> CampaignChapter:
        nonlocal _counter
        _counter += 1
        book_id = kwargs.get("book_id") or kwargs.get("book")
        if book_id and hasattr(book_id, "id"):
            book_id = book_id.id

        if "number" not in kwargs and book_id:
            count = await CampaignChapter.filter(book_id=book_id, is_archived=False).count()
            kwargs["number"] = count + 1
        elif "number" not in kwargs:
            kwargs["number"] = _counter

        defaults: dict[str, Any] = {
            "name": f"Test Chapter {_counter}",
        }
        defaults.update(kwargs)
        chapter = await CampaignChapter.create(**defaults)
        chapter = await CampaignChapter.get(id=str(chapter.id))
        created.append(chapter)
        return chapter

    yield _factory

    for chapter in created:
        with contextlib.suppress(Exception):
            await chapter.delete()


@pytest.fixture
async def pg_character_factory(pg_company_factory, pg_user_factory, pg_campaign_factory):
    """Return a factory that creates Tortoise Character instances.

    Auto-creates company, user, and campaign if not provided.
    """
    created: list[Character] = []
    _counter = 0

    async def _factory(**kwargs: Any) -> Character:
        nonlocal _counter
        _counter += 1

        # Auto-create a company when none is provided
        if "company" not in kwargs and "company_id" not in kwargs:
            kwargs["company"] = await pg_company_factory()

        if "user_creator" not in kwargs and "user_creator_id" not in kwargs:
            user = await pg_user_factory(company=kwargs.get("company"))
            kwargs["user_creator"] = user
        if "user_player" not in kwargs and "user_player_id" not in kwargs:
            kwargs["user_player"] = kwargs.get("user_creator") or await pg_user_factory(
                company=kwargs.get("company")
            )
        if "campaign" not in kwargs and "campaign_id" not in kwargs:
            kwargs["campaign"] = await pg_campaign_factory(company=kwargs.get("company"))

        defaults: dict[str, Any] = {
            "name_first": f"TestFirst{_counter}",
            "name_last": f"TestLast{_counter}",
            "character_class": "MORTAL",
            "type": "PLAYER",
            "game_version": "V5",
        }
        defaults.update(kwargs)
        character = await Character.create(**defaults)
        character = (
            await Character.filter(id=character.id)
            .prefetch_related(
                "concept",
                "vampire_attributes__clan",
                "werewolf_attributes__tribe",
                "werewolf_attributes__auspice",
                "mage_attributes",
                "hunter_attributes",
                "specialties",
            )
            .first()
        )
        created.append(character)
        return character

    yield _factory

    for character in created:
        with contextlib.suppress(Exception):
            await character.delete()


@pytest.fixture
async def pg_character_inventory_factory():
    """Return a factory that creates Tortoise CharacterInventory instances."""
    created: list[CharacterInventory] = []
    _counter = 0

    async def _factory(**kwargs: Any) -> CharacterInventory:
        nonlocal _counter
        _counter += 1
        defaults: dict[str, Any] = {
            "name": f"Test Item {_counter}",
            "type": "WEAPON",
        }
        defaults.update(kwargs)
        item = await CharacterInventory.create(**defaults)
        created.append(item)
        return item

    yield _factory

    for item in created:
        with contextlib.suppress(Exception):
            await item.delete()


@pytest.fixture
async def pg_specialty_factory():
    """Return a factory that creates Tortoise Specialty instances."""
    created: list[Specialty] = []
    _counter = 0

    async def _factory(**kwargs: Any) -> Specialty:
        nonlocal _counter
        _counter += 1
        defaults: dict[str, Any] = {
            "name": f"Test Specialty {_counter}",
            "type": "SKILL",
        }
        defaults.update(kwargs)
        specialty = await Specialty.create(**defaults)
        created.append(specialty)
        return specialty

    yield _factory

    for specialty in created:
        with contextlib.suppress(Exception):
            await specialty.delete()


@pytest.fixture
async def pg_character_trait_factory(pg_character_factory):
    """Return a factory that creates Tortoise CharacterTrait instances."""
    created: list[CharacterTrait] = []

    async def _factory(**kwargs: Any) -> CharacterTrait:
        # Auto-create a character when none is provided
        if "character" not in kwargs and "character_id" not in kwargs:
            kwargs["character"] = await pg_character_factory()

        # Auto-pick a trait when none is provided
        if "trait" not in kwargs and "trait_id" not in kwargs:
            kwargs["trait"] = await Trait.filter(is_archived=False).first()

        defaults: dict[str, Any] = {
            "value": 1,
        }
        defaults.update(kwargs)
        ct = await CharacterTrait.create(**defaults)
        ct = (
            await CharacterTrait.filter(id=ct.id)
            .prefetch_related(
                "trait", "trait__category", "trait__subcategory", "trait__sheet_section"
            )
            .first()
        )
        created.append(ct)
        return ct

    yield _factory

    for ct in created:
        with contextlib.suppress(Exception):
            await ct.delete()


@pytest.fixture
async def pg_vampire_attributes_factory():
    """Return a factory that creates Tortoise VampireAttributes instances."""
    created: list[VampireAttributes] = []

    async def _factory(**kwargs: Any) -> VampireAttributes:
        attrs = await VampireAttributes.create(**kwargs)
        created.append(attrs)
        return attrs

    yield _factory

    for attrs in created:
        with contextlib.suppress(Exception):
            await attrs.delete()


@pytest.fixture
async def pg_werewolf_attributes_factory():
    """Return a factory that creates Tortoise WerewolfAttributes instances."""
    created: list[WerewolfAttributes] = []

    async def _factory(**kwargs: Any) -> WerewolfAttributes:
        attrs = await WerewolfAttributes.create(**kwargs)
        created.append(attrs)
        return attrs

    yield _factory

    for attrs in created:
        with contextlib.suppress(Exception):
            await attrs.delete()
