"""Admin CLI."""

from __future__ import annotations

import asyncio
import logging

import click
from pydantic import ValidationError
from rich.console import Console

from vapi.db.models import Developer
from vapi.lib.database import setup_database

console = Console()

logger = logging.getLogger("vapi")


@click.group(name="developer", invoke_without_command=False, help="api-user commands")
def developer_group() -> None:
    """Group of api-user commands."""


@developer_group.command(name="create", help="Create an Developer")
@click.option(
    "--email",
    "-e",
    help="Email of the user",
    type=click.STRING,
    required=True,
    show_default=False,
)
@click.option(
    "--username",
    "-n",
    help="Username of the user",
    type=click.STRING,
    required=True,
    show_default=False,
)
@click.option("--global-admin", flag_value=True, help="Is this user a global admin")
def developer(*, email: str, username: str, global_admin: bool) -> None:
    """Create an Developer."""

    async def create_developer_async() -> None:
        await setup_database()

        existing_developer = await Developer.find_one(
            Developer.email == email, Developer.username == username, Developer.is_archived == False
        )
        if existing_developer:
            logger.info(
                "Developer already exists",
                extra={
                    "email": email,
                    "username": username,
                    "database_id": str(existing_developer.id),
                    "is_global_admin": existing_developer.is_global_admin,
                    "component": "cli",
                    "command": "developer create",
                },
            )
            raise click.Abort

        try:
            developer = Developer(email=email, username=username, is_global_admin=global_admin)
        except ValidationError as e:
            logger.exception(
                "Error creating Developer",
                extra={"error": e, "component": "cli", "command": "developer create"},
            )
            raise click.Abort from e

        await developer.save()
        api_key = await developer.generate_api_key()

        logger.info(
            "Developer created. Save the API key as it will not be displayed again.",
            extra={
                "database_id": str(developer.id),
                "email": developer.email,
                "username": developer.username,
                "api_key": api_key,
                "is_global_admin": developer.is_global_admin,
                "component": "cli",
                "command": "developer create",
            },
        )

    asyncio.run(create_developer_async())


@developer_group.command(name="list", help="List all Developers")
def list_developers() -> None:
    """List all Developers."""

    async def list_developers_async() -> None:
        await setup_database()

        developers = await Developer.find_all().to_list()
        console.rule("Developers")
        for developer in developers:
            console.print(f"[underline]id:          {developer.id}")
            console.print(f"Name:        {developer.name}")
            console.print(f"Email:       {developer.email}")
            console.print(f"Is archived: {developer.is_archived}")
            console.print(f"Is admin:    {developer.is_global_admin}")
            console.print(f"Slug:        {developer.slug}")
            console.print(f"Company permissions: {developer.companies}")
            console.print()

    asyncio.run(list_developers_async())


@developer_group.command(name="delete", help="Delete an Developer")
@click.argument("database_id")
def delete_developer(database_id: str) -> None:
    """Delete an Developer."""

    async def delete_developer_async() -> None:
        await setup_database()

        try:
            developer = await Developer.get(database_id)
        except ValueError as e:
            click.echo(f"Developer with ID '{database_id}' not found")
            raise click.Abort from e
        if not developer:
            click.echo(f"Developer with ID '{database_id}' not found")
            raise click.Abort

        await developer.delete()

        console.rule("Developer deleted")
        console.print(f"ID: {developer.id}")
        console.print(f"Name: {developer.name}")
        console.print(f"Email: {developer.email}")
        console.print(f"API key: [green bold]{developer.api_key}[/green bold]")
        console.print(f"Permissions: {developer.permissions.name}")

    asyncio.run(delete_developer_async())
