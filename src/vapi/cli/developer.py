"""Admin CLI."""

import asyncio
import logging

import click
from rich.console import Console
from tortoise import Tortoise

from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.domain.services.developer_svc import DeveloperService
from vapi.lib.database import init_tortoise

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
def developer(
    *,
    email: str,
    username: str,
    global_admin: bool,
) -> None:
    """Create an Developer."""

    async def create_developer_async() -> None:
        await init_tortoise()
        try:
            existing_developer = await Developer.filter(
                email=email, username=username, is_archived=False
            ).first()
            if existing_developer:
                logger.info(
                    "Developer already exists, skipping creation",
                    extra={
                        "email": email,
                        "username": username,
                        "database_id": str(existing_developer.id),
                        "is_global_admin": existing_developer.is_global_admin,
                        "component": "cli",
                        "command": "developer create",
                    },
                )
                return

            try:
                new_developer = await Developer.create(
                    email=email,
                    username=username,
                    is_global_admin=global_admin,
                )
            except Exception as e:
                logger.exception(
                    "Error creating Developer",
                    extra={"error": e, "component": "cli", "command": "developer create"},
                )
                raise click.Abort from e

            api_key = await DeveloperService().generate_api_key(new_developer)

            logger.info(
                "Developer created. Save the API key as it will not be displayed again.",
                extra={
                    "database_id": str(new_developer.id),
                    "email": new_developer.email,
                    "username": new_developer.username,
                    "api_key": api_key,
                    "is_global_admin": new_developer.is_global_admin,
                    "component": "cli",
                    "command": "developer create",
                },
            )
        finally:
            await Tortoise.close_connections()

    asyncio.run(create_developer_async())


@developer_group.command(name="list", help="List all Developers")
def list_developers() -> None:
    """List all Developers."""

    async def list_developers_async() -> None:
        await init_tortoise()
        try:
            developers = await Developer.all()
            console.rule("Developers")
            for dev in developers:
                permissions = await DeveloperCompanyPermission.filter(
                    developer_id=dev.id
                ).prefetch_related("company")
                company_perms = [f"{perm.company.name}:{perm.permission}" for perm in permissions]
                console.print(f"[underline]id:          {dev.id}")
                console.print(f"Username:    {dev.username}")
                console.print(f"Email:       {dev.email}")
                console.print(f"Is archived: {dev.is_archived}")
                console.print(f"Is admin:    {dev.is_global_admin}")
                console.print(f"Company permissions: {company_perms}")
                console.print()
        finally:
            await Tortoise.close_connections()

    asyncio.run(list_developers_async())


@developer_group.command(name="delete", help="Delete an Developer")
@click.argument("database_id")
def delete_developer(database_id: str) -> None:
    """Delete an Developer."""

    async def delete_developer_async() -> None:
        await init_tortoise()
        try:
            dev = await Developer.filter(id=database_id).first()
            if not dev:
                click.echo(f"Developer with ID '{database_id}' not found")
                raise click.Abort

            await dev.delete()

            console.rule("Developer deleted")
            console.print(f"ID: {dev.id}")
            console.print(f"Username: {dev.username}")
            console.print(f"Email: {dev.email}")
        finally:
            await Tortoise.close_connections()

    asyncio.run(delete_developer_async())
