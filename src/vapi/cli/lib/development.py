"""Dummy data for the database."""

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

console = Console()

logger = logging.getLogger("vapi")


async def create_developers() -> list[Developer]:
    """Create a Developer."""
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


async def create_companies(developers: list[Developer], num_companies: int) -> list[Company]:
    """Create a company."""
    # Find the non-global admin Developer
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


async def create_users(companies: list[Company], num_users: int) -> list[User]:
    """Create a user."""
    users: list[User] = []
    for company in companies:
        for i, _ in enumerate(range(num_users)):
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


async def create_campaigns(companies: list[Company], num_campaigns: int) -> list[Campaign]:
    """Create a campaign."""
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


async def create_characters(
    campaigns: list[Campaign], users: list[User], num_characters: int
) -> list[Character]:
    """Create a character."""
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


async def generate_api_key_for_developers(developers: list[Developer]) -> list[APIKeyUser]:
    """Generate a API key for an Developer."""
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


def write_api_keys_to_file(api_key_users: list[APIKeyUser]) -> None:
    """Write the API keys to a file."""
    DEV_FOLDER.mkdir(parents=True, exist_ok=True)

    if API_KEYS_FILE.exists():
        API_KEYS_FILE.unlink()
    API_KEYS_FILE.touch(exist_ok=True)

    for user in api_key_users:
        with API_KEYS_FILE.open("a") as f:
            f.write(f"""\
id:              {user.developer_id}
username:        {user.developer_name}
email:           {user.developer_email}
is global admin: {user.developer_is_global_admin}
api key:         {user.api_key}
\n""")

    console.print(f"API keys saved to [green bold]{API_KEYS_FILE}[/green bold]\n")


def write_api_keys_to_stdout(api_key_users: list[APIKeyUser], companies: list[Company]) -> None:
    """Write the API keys to stdout."""
    console.rule("API Keys")
    console.print(
        "[bold red]Please save the API keys as they will not be displayed again.[/bold red]"
    )

    for user in api_key_users:
        console.print(f"[underline]id:              {user.developer_id}")
        console.print(f"Name:            {user.developer_name}")
        console.print(f"Email:           {user.developer_email}")
        console.print(f"API key:         [green bold]{user.api_key}[/green bold]")
        console.print(f"Is global admin: {user.developer_is_global_admin}")
        console.print(f"Companies:       {(', '.join([str(x.id) for x in companies]))}")
        console.print()
