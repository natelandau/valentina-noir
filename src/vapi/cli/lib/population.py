"""PopulationService for creating dummy development data."""

import logging
import random

import click
from rich.console import Console

from vapi.cli.constants import API_KEYS_FILE, DEV_FOLDER
from vapi.cli.schemas import APIKeyUser
from vapi.constants import CharacterType, CompanyPermission, UserRole
from vapi.db.sql_models.campaign import Campaign, CampaignBook, CampaignChapter
from vapi.db.sql_models.company import Company, CompanySettings
from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.db.sql_models.user import User
from vapi.domain.handlers.character_autogeneration.handler import CharacterAutogenerationHandler
from vapi.domain.services.developer_svc import DeveloperService

logger = logging.getLogger("vapi")


class PopulationService:
    """Create dummy data for development environments."""

    def __init__(self) -> None:
        self.console = Console()
        self._developer_service = DeveloperService()

    async def populate(
        self,
        *,
        num_companies: int,
        num_users: int,
        num_campaigns: int,
        num_characters: int,
    ) -> None:
        """Orchestrate full population of a development database.

        Args:
            num_companies: Number of companies to create.
            num_users: Number of users to create per company.
            num_campaigns: Number of campaigns to create per company.
            num_characters: Number of characters to create per campaign.
        """
        developers = await self._create_developers()
        companies = await self._create_companies(developers=developers, num_companies=num_companies)
        users = await self._create_users(companies=companies, num_users=num_users)
        campaigns = await self._create_campaigns(companies=companies, num_campaigns=num_campaigns)
        await self._create_characters(
            campaigns=campaigns, users=users, num_characters=num_characters
        )
        api_key_users = await self._generate_api_keys(developers=developers, companies=companies)
        self.write_api_keys_to_stdout(api_key_users=api_key_users)
        self.write_api_keys_to_file(api_key_users=api_key_users)

    async def _create_developers(self) -> list[Developer]:
        """Create developer accounts for testing."""
        global_admin = await Developer.create(
            is_global_admin=True, username="dev-admin", email="admin@test.dev"
        )
        non_global_admin = await Developer.create(
            is_global_admin=False, username="dev-user", email="user@test.dev"
        )

        logger.info(
            "Created 2 Developers",
            extra={"component": "cli", "command": "development create_developers"},
        )
        return [global_admin, non_global_admin]

    async def _create_companies(
        self, developers: list[Developer], num_companies: int
    ) -> list[Company]:
        """Create companies and assign the non-global-admin developer to them."""
        non_global_admin_developer = next(
            (developer for developer in developers if not developer.is_global_admin), None
        )
        if not non_global_admin_developer:
            logger.error(
                "Error populating database. Run this command again.",
                extra={"component": "cli", "command": "development create_companies"},
            )
            raise click.Abort

        companies: list[Company] = []
        for i in range(num_companies):
            company = await Company.create(
                name=f"Company {i + 1}", email=f"company{i + 1}@test.dev"
            )
            await CompanySettings.create(company=company)
            companies.append(company)
            if i != 0:
                await DeveloperCompanyPermission.create(
                    developer=non_global_admin_developer,
                    company=company,
                    permission=CompanyPermission.ADMIN,
                )
        logger.info(
            "Created companies",
            extra={
                "num_created": len(companies),
                "component": "cli",
                "command": "development create_companies",
            },
        )
        return companies

    async def _create_users(self, companies: list[Company], num_users: int) -> list[User]:
        """Create users for each company."""
        users: list[User] = []
        for company in companies:
            for i in range(num_users):
                role = (
                    UserRole.ADMIN
                    if i == 0
                    else random.choice([UserRole.PLAYER, UserRole.STORYTELLER])
                )
                user = await User.create(
                    company=company,
                    role=role,
                    username=f"user-{i}-{company.id}",
                    email=f"user{i}@{company.id}.dev",
                )
                users.append(user)

        logger.info(
            "Created users",
            extra={
                "num_created": len(users),
                "component": "cli",
                "command": "development create_users",
            },
        )
        return users

    async def _create_campaigns(
        self, companies: list[Company], num_campaigns: int
    ) -> list[Campaign]:
        """Create campaigns with books and chapters for each company."""
        campaigns: list[Campaign] = []
        for company in companies:
            for c in range(num_campaigns):
                campaign = await Campaign.create(company=company, name=f"Campaign {c + 1}")
                campaigns.append(campaign)

                for i in range(2):
                    campaign_book = await CampaignBook.create(
                        campaign=campaign, number=i + 1, name=f"Book {i + 1}"
                    )

                    for j in range(2):
                        await CampaignChapter.create(
                            book=campaign_book, number=j + 1, name=f"Chapter {j + 1}"
                        )

        logger.info(
            "Created campaigns",
            extra={
                "num_created": len(campaigns),
                "component": "cli",
                "command": "development create_campaigns",
            },
        )
        return campaigns

    async def _create_characters(
        self, campaigns: list[Campaign], users: list[User], num_characters: int
    ) -> list:
        """Create characters for each campaign."""
        characters: list = []

        for campaign in campaigns:
            company = await Company.filter(id=campaign.company_id).first()  # type: ignore[attr-defined]
            for _ in range(num_characters):
                user = random.choice(users)
                chargen = CharacterAutogenerationHandler(
                    company=company,
                    user=user,
                    campaign=campaign,
                )
                character = await chargen.generate_character(
                    character_type=CharacterType.PLAYER,
                )
                characters.append(character)

        logger.info(
            "Created characters",
            extra={
                "num_created": len(characters),
                "component": "cli",
                "command": "development create_characters",
            },
        )
        return characters

    async def _generate_api_keys(
        self, developers: list[Developer], companies: list[Company]
    ) -> list[APIKeyUser]:
        """Generate API keys for all developer accounts."""
        api_key_users: list[APIKeyUser] = []
        for developer in developers:
            if developer.is_global_admin:
                company_ids = [c.id for c in companies]
            else:
                await developer.fetch_related("permissions")
                company_ids = [p.company_id for p in developer.permissions]  # type: ignore[attr-defined]

            api_key_users.append(
                APIKeyUser(
                    api_key=await self._developer_service.generate_api_key(developer),
                    developer_id=developer.id,
                    developer_name=developer.username,
                    developer_email=developer.email,
                    developer_is_global_admin=developer.is_global_admin,
                    company_ids=company_ids,
                ),
            )
        return api_key_users

    def write_api_keys_to_file(self, api_key_users: list[APIKeyUser]) -> None:
        """Write the API keys to a file for later reference."""
        DEV_FOLDER.mkdir(parents=True, exist_ok=True)

        if API_KEYS_FILE.exists():
            API_KEYS_FILE.unlink()
        API_KEYS_FILE.touch(exist_ok=True)

        with API_KEYS_FILE.open("a") as f:
            for user in api_key_users:
                companies = ", ".join(str(c) for c in user.company_ids)
                f.write(f"""\
id:              {user.developer_id}
Name:            {user.developer_name}
Email:           {user.developer_email}
API key:         {user.api_key}
Is global admin: {user.developer_is_global_admin}
Companies:       {companies}
\n""")

        self.console.print(f"API keys saved to [green bold]{API_KEYS_FILE}[/green bold]\n")

    def write_api_keys_to_stdout(self, api_key_users: list[APIKeyUser]) -> None:
        """Write the API keys to stdout."""
        self.console.rule("API Keys")
        self.console.print(
            "[bold red]Please save the API keys as they will not be displayed again.[/bold red]"
        )

        for user in api_key_users:
            companies = ", ".join(str(c) for c in user.company_ids)
            self.console.print(f"[underline]id:              {user.developer_id}")
            self.console.print(f"Name:            {user.developer_name}")
            self.console.print(f"Email:           {user.developer_email}")
            self.console.print(f"API key:         [green bold]{user.api_key}[/green bold]")
            self.console.print(f"Is global admin: {user.developer_is_global_admin}")
            self.console.print(f"Companies:       {companies}")
            self.console.print()
