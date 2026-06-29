"""Dev-only: reset, seed, and populate the development database with varied test data.

Run as a module so scripts.dev_data resolves consistently:

    uv run python -m scripts.populate_dev_db [--companies N ...] [--reset-only] [--force] [--yes]
"""

import asyncio

import click
from rich.console import Console
from rich.prompt import Confirm
from tortoise import Tortoise

from scripts.dev_data.api_keys import write_api_keys_to_file, write_api_keys_to_stdout
from scripts.dev_data.bootstrap import reset_database
from scripts.dev_data.config import PopulateConfig
from scripts.dev_data.generators import build_api_keys, populate_data
from scripts.dev_data.safety import production_warning
from vapi.config import settings

console = Console()


async def _run(*, cfg: PopulateConfig, reset_only: bool) -> None:
    """Reset the database and (unless reset_only) populate it, then print API keys."""
    try:
        await reset_database()
        if reset_only:
            console.print("[green]Database reset complete.[/green]")
            return
        developers = await populate_data(cfg)
        keys = await build_api_keys(developers)
        write_api_keys_to_stdout(keys)
        write_api_keys_to_file(keys)
    finally:
        # Close in all paths, including a failure inside reset_database after Tortoise init.
        await Tortoise.close_connections()


@click.command(help="Reset and populate the development database with varied test data.")
@click.option(
    "--companies", "num_companies", type=click.IntRange(min=1), default=PopulateConfig.num_companies
)
@click.option("--users", "num_users", type=click.IntRange(min=1), default=PopulateConfig.num_users)
@click.option(
    "--campaigns", "num_campaigns", type=click.IntRange(min=1), default=PopulateConfig.num_campaigns
)
@click.option(
    "--characters",
    "num_characters",
    type=click.IntRange(min=0),
    default=PopulateConfig.num_characters,
)
@click.option("--reset-only", is_flag=True, help="Drop, recreate, and seed only; do not populate.")
@click.option("--force", is_flag=True, help="Override the production-target safety guard.")
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
def main(
    *,
    num_companies: int,
    num_users: int,
    num_campaigns: int,
    num_characters: int,
    reset_only: bool,
    force: bool,
    yes: bool,
) -> None:
    """Entry point for `python -m scripts.populate_dev_db`."""
    pg = settings.postgres
    warning = production_warning(settings)  # type: ignore[arg-type] # ty:ignore[invalid-argument-type]
    if warning and not force:
        console.print(
            f"[bold red]Refusing to run against a production-like target:[/bold red] {warning}.\n"
            f"Target: {pg.host}:{pg.port}/{pg.database} (debug={settings.debug}). "
            "Pass --force to override."
        )
        raise SystemExit(1)

    action = "reset" if reset_only else "reset and populate"
    console.print(
        f"About to [bold red]{action}[/bold red] the database at "
        f"[green bold]{pg.host}:{pg.port}/{pg.database}[/green bold] (debug={settings.debug})."
    )
    if not yes and not Confirm.ask("This will DELETE all existing data. Continue?"):
        console.print("Aborting...")
        return

    cfg = PopulateConfig(
        num_companies=num_companies,
        num_users=num_users,
        num_campaigns=num_campaigns,
        num_characters=num_characters,
    )
    asyncio.run(_run(cfg=cfg, reset_only=reset_only))


if __name__ == "__main__":
    main()
