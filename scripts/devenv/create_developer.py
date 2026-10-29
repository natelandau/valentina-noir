"""Create a developer and record its raw API key for the connection sheet.

python -m scripts.devenv.create_developer --username U --email E [--global-admin]
"""

import click
from rich.console import Console

from scripts.dev_data.api_keys import DevApiKey
from scripts.devenv.keys import record_keys
from vapi.cli.lib.runner import run_with_tortoise
from vapi.db.sql_models.developer import Developer
from vapi.domain.services.developer_svc import DeveloperService

console = Console()


async def _create(*, username: str, email: str, global_admin: bool) -> None:
    developer = await Developer.create(username=username, email=email, is_global_admin=global_admin)
    api_key = await DeveloperService().generate_api_key(developer)
    record_keys(
        [
            DevApiKey(
                api_key=api_key,
                developer_id=developer.id,
                username=username,
                email=email,
                is_global_admin=global_admin,
            )
        ],
        replace=False,
    )
    console.print(f"Developer [bold]{username}[/bold] created: {developer.id}")


@click.command(help="Create a developer and record its API key.")
@click.option("--username", required=True)
@click.option("--email", required=True)
@click.option("--global-admin", is_flag=True)
def main(*, username: str, email: str, global_admin: bool) -> None:
    """Entry point for `python -m scripts.devenv.create_developer`."""
    run_with_tortoise(_create(username=username, email=email, global_admin=global_admin))


if __name__ == "__main__":
    main()
