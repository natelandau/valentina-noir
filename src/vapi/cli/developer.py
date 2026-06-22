"""Admin CLI."""

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

import click
from rich.console import Console
from tortoise.expressions import Q

from vapi.cli.lib.runner import run_with_tortoise
from vapi.db.sql_models.developer import Developer, DeveloperCompanyPermission
from vapi.domain.services.developer_svc import DeveloperService

if TYPE_CHECKING:
    from uuid import UUID

console = Console()

logger = logging.getLogger("vapi")


@click.group(name="developer", invoke_without_command=False, help="api-user commands")
def developer_group() -> None:
    """Group the admin commands for creating, listing, and deleting developer accounts."""


async def _create_developer(*, email: str, username: str, global_admin: bool) -> None:
    """Create a developer account and print its one-time API key.

    Args:
        email: Email of the developer.
        username: Username of the developer.
        global_admin: Whether the developer is a global admin.
    """
    # Email and username are independently unique, so match either one: an existing
    # developer that shares only the email (or only the username) still collides.
    existing_developer = await Developer.filter(
        Q(email=email) | Q(username=username), is_archived=False
    ).first()
    if existing_developer:
        collisions = [
            field
            for field, value in (("email", email), ("username", username))
            if getattr(existing_developer, field) == value
        ]
        logger.info(
            "Developer already exists, skipping creation",
            extra={
                "email": email,
                "username": username,
                "collision_fields": collisions,
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


@developer_group.command(name="create", help="Create a Developer")
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
    """Create a Developer."""
    run_with_tortoise(_create_developer(email=email, username=username, global_admin=global_admin))


async def _list_developers() -> None:
    """Print every developer with its company permissions."""
    developers = await Developer.all()

    # Load every developer's permissions in one query instead of one per developer.
    perms_by_developer: dict[UUID, list[DeveloperCompanyPermission]] = defaultdict(list)
    if developers:
        permissions = await DeveloperCompanyPermission.filter(
            developer_id__in=[dev.id for dev in developers]
        ).prefetch_related("company")
        for perm in permissions:
            perms_by_developer[perm.developer_id].append(perm)  # type: ignore[attr-defined]

    console.rule("Developers")
    for dev in developers:
        company_perms = [
            f"{perm.company.name}:{perm.permission}" for perm in perms_by_developer[dev.id]
        ]
        console.print(f"[underline]id:          {dev.id}")
        console.print(f"Username:    {dev.username}")
        console.print(f"Email:       {dev.email}")
        console.print(f"Is archived: {dev.is_archived}")
        console.print(f"Is admin:    {dev.is_global_admin}")
        console.print(f"Company permissions: {company_perms}")
        console.print()


@developer_group.command(name="list", help="List all Developers")
def list_developers() -> None:
    """List all Developers."""
    run_with_tortoise(_list_developers())


async def _delete_developer(database_id: str) -> None:
    """Delete a developer by database id.

    Args:
        database_id: The primary key of the developer to delete.
    """
    dev = await Developer.filter(id=database_id).first()
    if not dev:
        click.echo(f"Developer with ID '{database_id}' not found")
        raise click.Abort

    await dev.delete()

    console.rule("Developer deleted")
    console.print(f"ID: {dev.id}")
    console.print(f"Username: {dev.username}")
    console.print(f"Email: {dev.email}")


@developer_group.command(name="delete", help="Delete a Developer")
@click.argument("database_id")
def delete_developer(database_id: str) -> None:
    """Delete a Developer."""
    run_with_tortoise(_delete_developer(database_id))
