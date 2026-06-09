"""Generators that fill a seeded database with believable, varied dev data."""

import random
import uuid
from dataclasses import dataclass
from uuid import UUID

from scripts.dev_data import fake
from scripts.dev_data.api_keys import DevApiKey
from scripts.dev_data.config import (
    CLASS_COVERAGE,
    CLASS_POOL,
    TYPE_COVERAGE,
    TYPE_WEIGHTED_POOL,
    PopulateConfig,
)
from vapi.constants import (
    CharacterClass,
    CharacterType,
    CompanyPermission,
    DiceSize,
    InventoryItemType,
    UserRole,
)
from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.character import Character, CharacterInventory
from vapi.db.sql_models.character_sheet import Trait
from vapi.db.sql_models.company import Company, CompanySettings
from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.db.sql_models.notes import Note
from vapi.db.sql_models.quickroll import QuickRoll
from vapi.db.sql_models.user import User
from vapi.domain.controllers.dicerolls.dto import DiceRollCreate
from vapi.domain.handlers.character_autogeneration.handler import CharacterAutogenerationHandler
from vapi.domain.services.developer_svc import DeveloperService
from vapi.domain.services.diceroll_svc import DiceRollService


@dataclass
class DevAccounts:
    """The three developer tiers created for testing."""

    global_admin: Developer
    company_admin: Developer
    company_user: Developer

    def as_list(self) -> list[Developer]:
        """Return the developers in a stable order."""
        return [self.global_admin, self.company_admin, self.company_user]


def _count(rng: tuple[int, int]) -> int:
    """Pick a random integer in the inclusive (low, high) range."""
    return random.randint(rng[0], rng[1])


def _uuid(val: object) -> uuid.UUID:
    """Convert any UUID-like object (including uuid_utils.UUID) to a stdlib uuid.UUID.

    Tortoise's UUIDField.to_python_value() calls uuid.UUID(value) expecting a string
    when it receives an already-UUID value. uuid_utils.UUID objects (which Tortoise
    uses for primary keys) don't have the .replace() method that stdlib uuid.UUID.__init__
    expects, so they must be converted via str() before being passed to .create() calls
    that use the _id suffix form (e.g. company_id=...).
    """
    return uuid.UUID(str(val))


async def create_developers() -> DevAccounts:
    """Create one developer of each tier: global admin, company admin, non-admin."""
    global_admin = await Developer.create(
        username="dev-global", email="global@test.dev", is_global_admin=True
    )
    company_admin = await Developer.create(
        username="dev-admin", email="admin@test.dev", is_global_admin=False
    )
    company_user = await Developer.create(
        username="dev-user", email="user@test.dev", is_global_admin=False
    )
    return DevAccounts(
        global_admin=global_admin, company_admin=company_admin, company_user=company_user
    )


async def create_companies(accounts: DevAccounts, cfg: PopulateConfig) -> list[Company]:
    """Create companies with settings; grant the non-global developers their permissions."""
    companies: list[Company] = []
    for _ in range(cfg.num_companies):
        company = await Company.create(name=fake.company_name(), email=fake.email())
        await CompanySettings.create(company=company)
        await DeveloperCompanyPermission.create(
            developer=accounts.company_admin,
            company=company,
            permission=CompanyPermission.ADMIN,
        )
        await DeveloperCompanyPermission.create(
            developer=accounts.company_user,
            company=company,
            permission=CompanyPermission.USER,
        )
        companies.append(company)
    return companies


async def create_users(companies: list[Company], cfg: PopulateConfig) -> dict[str, list[User]]:
    """Create users per company with guaranteed ADMIN/STORYTELLER/PLAYER coverage.

    Keyed by str(company.id): downstream lookups use FK ids from refreshed rows, which
    can be a different UUID subtype than Company.create() returns, so we normalize to str.
    """
    coverage = [UserRole.ADMIN, UserRole.STORYTELLER, UserRole.PLAYER]
    users_by_company: dict[str, list[User]] = {}
    for company in companies:
        company_users: list[User] = []
        for i in range(cfg.num_users):
            role = (
                coverage[i]
                if i < len(coverage)
                else random.choice([UserRole.PLAYER, UserRole.STORYTELLER])
            )
            first, last = fake.person_name()
            user = await User.create(
                company=company,
                role=role,
                username=fake.username(),
                email=fake.email(),
                name_first=first,
                name_last=last,
            )
            company_users.append(user)
        users_by_company[str(company.id)] = company_users
    return users_by_company


async def create_campaigns(
    companies: list[Company], cfg: PopulateConfig
) -> tuple[list[Campaign], list[CampaignBook]]:
    """Create campaigns with books and chapters for each company."""
    campaigns: list[Campaign] = []
    books: list[CampaignBook] = []
    for company in companies:
        for _ in range(cfg.num_campaigns):
            campaign = await Campaign.create(company=company, name=fake.campaign_title())
            campaigns.append(campaign)
            for b in range(cfg.books_per_campaign):
                book = await CampaignBook.create(
                    campaign=campaign, number=b + 1, name=fake.book_title()
                )
                books.append(book)
                for c in range(cfg.chapters_per_book):
                    await CampaignChapter.create(book=book, number=c + 1, name=fake.chapter_title())
    return campaigns, books


def _character_type_for_index(index: int) -> CharacterType:
    """First three indices guarantee type coverage; the rest favor PLAYER."""
    if index < len(TYPE_COVERAGE):
        return TYPE_COVERAGE[index]
    return random.choice(TYPE_WEIGHTED_POOL)


def _character_class_for_index(index: int) -> CharacterClass:
    """First four indices guarantee a vampire/werewolf/mortal/hunter mix; rest random."""
    if index < len(CLASS_COVERAGE):
        return CLASS_COVERAGE[index]
    return random.choice(CLASS_POOL)


async def create_characters(
    campaigns: list[Campaign],
    companies: list[Company],
    users_by_company: dict[str, list[User]],
    cfg: PopulateConfig,
) -> list[Character]:
    """Generate characters across types and classes via the autogeneration handler."""
    companies_by_id = {str(company.id): company for company in companies}
    characters: list[Character] = []
    for campaign in campaigns:
        company = companies_by_id[str(campaign.company_id)]
        company_users = users_by_company[str(campaign.company_id)]
        for i in range(cfg.num_characters):
            user = random.choice(company_users)
            handler = CharacterAutogenerationHandler(user=user, company=company, campaign=campaign)
            character = await handler.generate_character(
                character_type=_character_type_for_index(i),
                char_class=_character_class_for_index(i),
            )
            characters.append(character)
    return characters


async def create_inventory(characters: list[Character], cfg: PopulateConfig) -> None:
    """Give each character a random handful of inventory items across item types."""
    item_types = list(InventoryItemType)
    for character in characters:
        for _ in range(_count(cfg.inventory_per_char)):
            await CharacterInventory.create(
                character=character,
                name=fake.inventory_item_name(),
                type=random.choice(item_types),
            )


async def create_dice_rolls(
    characters: list[Character],
    users_by_company: dict[str, list[User]],
    cfg: PopulateConfig,
) -> None:
    """Record dice rolls (with results) per character via the production service."""
    service = DiceRollService()
    dice_sizes = list(DiceSize)
    for character in characters:
        company_users = users_by_company[str(character.company_id)]
        # Normalize uuid_utils.UUID FK ids to stdlib uuid.UUID before passing them as
        # _id-form values (Tortoise's UUIDField conversion rejects uuid_utils.UUID).
        company_id = _uuid(character.company_id)
        character_id = _uuid(character.id)
        campaign_id = _uuid(character.campaign_id) if character.campaign_id else None
        for _ in range(_count(cfg.dice_rolls_per_char)):
            user = random.choice(company_users)
            data = DiceRollCreate(
                difficulty=random.randint(2, 8),
                dice_size=random.choice(dice_sizes),
                num_dice=random.randint(1, 8),
                num_desperation_dice=random.randint(0, 2),
                comment=fake.dice_comment(),
                campaign_id=campaign_id,
                character_id=character_id,
            )
            await service.create_complete_dice_roll(
                data=data, company_id=company_id, user_id=_uuid(user.id)
            )


async def create_quick_rolls(users_by_company: dict[str, list[User]], cfg: PopulateConfig) -> None:
    """Create saved quick-roll templates per user, each with a few random traits."""
    available_traits = await Trait.filter(is_archived=False).limit(50)
    for users in users_by_company.values():
        for user in users:
            for _ in range(_count(cfg.quick_rolls_per_user)):
                quick_roll = await QuickRoll.create(
                    user=user,
                    name=fake.quick_roll_name(),
                    description=fake.note_body(),
                )
                if available_traits:
                    sample = random.sample(
                        available_traits,
                        k=min(_count(cfg.traits_per_quick_roll), len(available_traits)),
                    )
                    await quick_roll.traits.add(*sample)


async def create_notes(
    campaigns: list[Campaign],
    books: list[CampaignBook],
    characters: list[Character],
    users_by_company: dict[str, list[User]],
    cfg: PopulateConfig,
) -> None:
    """Attach notes independently to campaigns, books, and characters."""

    def _author(company_id: UUID) -> User:
        return random.choice(users_by_company[str(company_id)])

    for campaign in campaigns:
        for _ in range(_count(cfg.notes_per_target)):
            await Note.create(
                company_id=_uuid(campaign.company_id),
                user=_author(campaign.company_id),
                campaign=campaign,
                title=fake.note_title(),
                content=fake.note_body(),
            )
    for book in books:
        campaign = await Campaign.get(id=book.campaign_id)
        for _ in range(_count(cfg.notes_per_target)):
            await Note.create(
                company_id=_uuid(campaign.company_id),
                user=_author(campaign.company_id),
                book=book,
                title=fake.note_title(),
                content=fake.note_body(),
            )
    for character in characters:
        for _ in range(_count(cfg.notes_per_target)):
            await Note.create(
                company_id=_uuid(character.company_id),
                user=_author(character.company_id),
                character=character,
                title=fake.note_title(),
                content=fake.note_body(),
            )


async def populate_data(cfg: PopulateConfig) -> list[Developer]:
    """Run every generator in dependency order; return the developers for key output.

    Assumes Tortoise is initialized and reference data is seeded. Does NOT reset the
    database, so it is safe to call from tests against the seeded test database.
    """
    accounts = await create_developers()
    companies = await create_companies(accounts, cfg)
    users_by_company = await create_users(companies, cfg)
    campaigns, books = await create_campaigns(companies, cfg)
    characters = await create_characters(campaigns, companies, users_by_company, cfg)
    await create_inventory(characters, cfg)
    await create_dice_rolls(characters, users_by_company, cfg)
    await create_quick_rolls(users_by_company, cfg)
    await create_notes(campaigns, books, characters, users_by_company, cfg)
    return accounts.as_list()


async def build_api_keys(developers: list[Developer]) -> list[DevApiKey]:
    """Generate an API key per developer and capture its access tier."""
    service = DeveloperService()
    keys: list[DevApiKey] = []
    for developer in developers:
        await developer.fetch_related("permissions")
        company_permissions = [
            (p.company_id, p.permission)
            for p in developer.permissions  # type: ignore[attr-defined]
        ]
        keys.append(
            DevApiKey(
                api_key=await service.generate_api_key(developer),
                developer_id=developer.id,
                username=developer.username,
                email=developer.email,
                is_global_admin=developer.is_global_admin,
                company_permissions=company_permissions,
            )
        )
    return keys
