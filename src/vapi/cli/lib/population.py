"""PopulationService for creating dummy development data."""

import logging
import random

import click
from rich.console import Console

from vapi.cli.constants import API_KEYS_FILE, DEV_FOLDER
from vapi.cli.lib import factories
from vapi.cli.schemas import APIKeyUser
from vapi.constants import CharacterType, CompanyPermission, UserRole
from vapi.db.models import (
    Campaign,
    Character,
    Company,
    Developer,
    User,
)
from vapi.db.models.developer import CompanyPermissions
from vapi.domain.handlers.character_autogeneration.handler import CharacterAutogenerationHandler

logger = logging.getLogger("vapi")


class PopulationService:
    """Create dummy data for development environments."""

    def __init__(self) -> None:
        self.console = Console()

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
        api_key_users = await self._generate_api_keys(developers=developers)
        self.write_api_keys_to_stdout(api_key_users=api_key_users, companies=companies)
        self.write_api_keys_to_file(api_key_users=api_key_users)

    async def _create_developers(self) -> list[Developer]:
        """Create developer accounts for testing."""
        global_admin = factories.DeveloperFactory.build(
            model_version=1, is_global_admin=True, is_archived=False
        )
        await global_admin.save()
        non_global_admin = factories.DeveloperFactory.build(
            model_version=1, is_global_admin=False, is_archived=False
        )
        await non_global_admin.save()

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
            company = factories.CompanyFactory.build(model_version=1)
            await company.save()
            companies.append(company)
            if i != 0:
                non_global_admin_developer.companies.append(
                    CompanyPermissions(
                        company_id=company.id, name=company.name, permission=CompanyPermission.ADMIN
                    )
                )
                await non_global_admin_developer.save()
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
                if i == 0:
                    user = factories.UserFactory.build(company_id=company.id, role=UserRole.ADMIN)
                else:
                    user = factories.UserFactory.build(
                        company_id=company.id,
                        role=random.choice([UserRole.PLAYER, UserRole.STORYTELLER]),
                    )

                await user.save()
                users.append(user)
                company.user_ids.append(user.id)

            await company.save()
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
            for _ in range(num_campaigns):
                campaign = factories.CampaignFactory.build(company_id=company.id)
                await campaign.save()
                campaigns.append(campaign)

                for i in range(2):
                    campaign_book = factories.CampaignBookFactory.build(
                        campaign_id=campaign.id, number=i + 1
                    )
                    await campaign_book.save()

                    for j in range(2):
                        campaign_chapter = factories.CampaignChapterFactory.build(
                            book_id=campaign_book.id, number=j + 1
                        )
                        await campaign_chapter.save()

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
    ) -> list[Character]:
        """Create characters for each campaign."""
        characters: list[Character] = []

        for campaign in campaigns:
            company = await Company.get(campaign.company_id)
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

    async def _generate_api_keys(self, developers: list[Developer]) -> list[APIKeyUser]:
        """Generate API keys for all developer accounts."""
        return [
            APIKeyUser(
                api_key=await user.generate_api_key(),
                developer_id=user.id,
                developer_name=user.username,
                developer_email=user.email,
                developer_is_global_admin=user.is_global_admin,
            )
            for user in developers
        ]

    def write_api_keys_to_file(self, api_key_users: list[APIKeyUser]) -> None:
        """Write the API keys to a file for later reference."""
        DEV_FOLDER.mkdir(parents=True, exist_ok=True)

        if API_KEYS_FILE.exists():
            API_KEYS_FILE.unlink()
        API_KEYS_FILE.touch(exist_ok=True)

        with API_KEYS_FILE.open("a") as f:
            for user in api_key_users:
                f.write(f"""\
id:              {user.developer_id}
username:        {user.developer_name}
email:           {user.developer_email}
is global admin: {user.developer_is_global_admin}
api key:         {user.api_key}
\n""")

        self.console.print(f"API keys saved to [green bold]{API_KEYS_FILE}[/green bold]\n")

    def write_api_keys_to_stdout(
        self, api_key_users: list[APIKeyUser], companies: list[Company]
    ) -> None:
        """Write the API keys to stdout."""
        self.console.rule("API Keys")
        self.console.print(
            "[bold red]Please save the API keys as they will not be displayed again.[/bold red]"
        )

        for user in api_key_users:
            self.console.print(f"[underline]id:              {user.developer_id}")
            self.console.print(f"Name:            {user.developer_name}")
            self.console.print(f"Email:           {user.developer_email}")
            self.console.print(f"API key:         [green bold]{user.api_key}[/green bold]")
            self.console.print(f"Is global admin: {user.developer_is_global_admin}")
            self.console.print(f"Companies:       {(', '.join([str(x.id) for x in companies]))}")
            self.console.print()
