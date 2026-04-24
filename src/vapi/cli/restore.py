"""Restore CLI — drop the database and load a pg_dump backup.

Do NOT add ``from __future__ import annotations`` here: Click resolves some
hints at runtime and mixing deferred annotations with rich types has caused
issues elsewhere in this project.
"""

import asyncio
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Confirm

from vapi.config import settings
from vapi.lib.db_restore import (
    DatabaseRestoreService,
    LocalFileSource,
    RestoreSource,
    S3Source,
)
from vapi.lib.exceptions import DatabaseRestoreError

logger = logging.getLogger("vapi")
console = Console()

_RESTORE_HELP = (
    "Restore the database from a pg_dump backup. This DROPS and RECREATES "
    "the database — existing data is destroyed. By default, pulls the most "
    "recent backup from S3 (the db_backups/ prefix used by the scheduled "
    "backup task).\n\n"
    "After restoring an older backup, run `app migrate` separately to bring "
    "the schema up to date with the current code."
)


@click.command(name="restore", help=_RESTORE_HELP)
@click.option(
    "-f",
    "--file",
    "file",
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    default=None,
    help="Restore from a local .dump file instead of S3.",
)
@click.option(
    "--s3-path",
    "s3_path",
    type=click.STRING,
    default=None,
    help="Restore from a specific S3 key (e.g., db_backups/2026-04-15.dump). Default: latest.",
)
@click.option(
    "-y",
    "--yes",
    "yes",
    is_flag=True,
    default=False,
    help="Skip the confirmation prompt.",
)
def restore(*, file: Path | None, s3_path: str | None, yes: bool) -> None:
    """Restore the database from a pg_dump -Fc backup."""
    if file is not None and s3_path is not None:
        msg = "Options --file and --s3-path are mutually exclusive."
        raise click.UsageError(msg)

    source: RestoreSource
    if file is not None:
        source = LocalFileSource(path=file)
        source_description = f"local file [green bold]{file}[/green bold]"
    else:
        source = S3Source(key=s3_path)
        source_description = (
            f"S3 key [green bold]{s3_path}[/green bold]"
            if s3_path
            else "[green bold]latest S3 backup[/green bold]"
        )

    pg = settings.postgres
    if not yes:
        confirm = Confirm.ask(
            f"Are you sure you want to DROP and RESTORE the database at "
            f"[green bold]{pg.host}:{pg.port}/{pg.database}[/green bold] "
            f"from {source_description}?"
        )
        if not confirm:
            console.print("Aborting...")
            return

    service = DatabaseRestoreService()
    try:
        asyncio.run(service.run(source=source))
    except DatabaseRestoreError as e:
        console.print(f"[red]Restore failed:[/red] {e}")
        raise click.Abort from e

    console.print("Database restored.")
    console.print(
        "[yellow]Run `app migrate` next if the backup is older than the current schema.[/yellow]"
    )
