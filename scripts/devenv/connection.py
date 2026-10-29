"""Connection sheet: everything a developer needs to call one checkout's API.

Runs inside the stack's `api` container (`.dev` is bind-mounted), reading the stack's database:

    python -m scripts.devenv.connection --origin populated --project vapi-main \
        --ports-json '{"api": 24100, ...}'
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import click

from scripts.devenv.compose import (
    DOCKER_URL,
    HOST_URL,
    POSTGRES_DB,
    POSTGRES_PASSWORD,
    POSTGRES_USER,
)
from scripts.devenv.files import write_private
from scripts.devenv.keys import DEV_DIR, load_keys
from scripts.devenv.ports import StackPorts
from vapi.cli.lib.runner import run_with_tortoise
from vapi.db.sql_models.company import Company
from vapi.db.sql_models.developer import Developer
from vapi.db.sql_models.user import User

SHEET_DIR = DEV_DIR
API_PATH = "/api/v1"
POSTGRES_DSN = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@127.0.0.1"


@dataclass(frozen=True)
class DeveloperInfo:
    """A developer, its raw key when known, and its company permissions."""

    id: UUID
    username: str
    email: str
    is_global_admin: bool
    api_key: str | None
    permissions: list[tuple[UUID, str]] = field(default_factory=list)


@dataclass(frozen=True)
class CompanyInfo:
    """A company."""

    id: UUID
    name: str


@dataclass(frozen=True)
class UserInfo:
    """A user with its role and company."""

    id: UUID
    name: str
    role: str
    company_id: UUID


@dataclass(frozen=True)
class ConnectionData:
    """Database contents shown on the sheet."""

    origin: str
    developers: list[DeveloperInfo]
    companies: list[CompanyInfo]
    users: list[UserInfo]


def _user_name(user: User) -> str:
    full = " ".join(part for part in (user.name_first, user.name_last) if part)
    return full or user.username


async def gather_connection(*, keys: dict[UUID, str], origin: str) -> ConnectionData:
    """Read the sheet's developers, companies, and users from the database.

    Args:
        keys: Raw keys by developer ID. Keys of developers that no longer exist are ignored.
        origin: How the data got there, such as `populated` or `copied-from-main`.

    Returns:
        The non-archived rows.
    """
    developers = await Developer.filter(is_archived=False).prefetch_related("permissions")
    companies = await Company.filter(is_archived=False).order_by("name")
    users = await User.filter(is_archived=False, company__is_archived=False).order_by(
        "company_id", "role", "username"
    )

    return ConnectionData(
        origin=origin,
        developers=[
            DeveloperInfo(
                id=developer.id,
                username=developer.username,
                email=developer.email,
                is_global_admin=developer.is_global_admin,
                api_key=keys.get(developer.id),
                permissions=[
                    (permission.company_id, str(permission.permission))  # ty:ignore[unresolved-attribute]
                    for permission in developer.permissions
                ],
            )
            for developer in sorted(developers, key=lambda d: d.username)
        ],
        companies=[CompanyInfo(id=company.id, name=company.name) for company in companies],
        users=[
            UserInfo(
                id=user.id,
                name=_user_name(user),
                role=str(user.role),
                company_id=user.company_id,  # ty:ignore[unresolved-attribute]
            )
            for user in users
        ],
    )


def _access(developer: DeveloperInfo) -> str:
    if developer.is_global_admin:
        return "global admin"
    if not developer.permissions:
        return "no company access"
    return ", ".join(
        f"{permission} on {company_id}" for company_id, permission in developer.permissions
    )


def render_markdown(
    data: ConnectionData, *, ports: StackPorts, project: str, generated_at: datetime
) -> str:
    """Render the human-readable connection sheet.

    Args:
        data: Database contents.
        ports: The stack's published host ports.
        project: The Compose project name.
        generated_at: When the sheet was produced.

    Returns:
        Markdown text.
    """
    api_url = f"{HOST_URL}:{ports.api}"
    lines = [
        "# Connection sheet",
        "",
        f"- Compose project: `{project}`",
        f"- Generated at: {generated_at.isoformat()}",
        f"- Data origin: {data.origin}",
        f"- API URL: {api_url}{API_PATH}",
        f"- API URL from a container: {DOCKER_URL}:{ports.api}{API_PATH}",
        "",
        "## Ports",
        "",
        "| Service | Port |",
        "| --- | --- |",
        f"| API | {ports.api} |",
        f"| Postgres | {ports.postgres} |",
        f"| Redis | {ports.redis} |",
        f"| S3 | {ports.s3} |",
        f"| S3 console | {ports.s3_console} |",
        f"| Postgres (tests) | {ports.postgres_test} |",
        f"| Redis (tests) | {ports.redis_test} |",
        f"| debugpy | {ports.debugpy} (only when started with debug=true) |",
        "",
        "## Shell access",
        "",
        "```bash",
        f"psql {POSTGRES_DSN}:{ports.postgres}/{POSTGRES_DB}",
        f"redis-cli -h 127.0.0.1 -p {ports.redis}",
        "# Shortcuts that run inside the containers",
        "uv run duty psql",
        "uv run duty redis-cli",
        "```",
        "",
        "## Developers",
        "",
    ]
    for developer in data.developers:
        lines += [
            f"### {developer.username}",
            "",
            f"- ID: `{developer.id}`",
            f"- Email: {developer.email}",
            f"- Access: {_access(developer)}",
        ]
        if developer.api_key is None:
            lines += ["- API key: key not recorded", ""]
            continue
        lines += [
            f"- API key: `{developer.api_key}`",
            "",
            "```bash",
            f'curl -H "X-API-KEY: {developer.api_key}" {api_url}{API_PATH}/companies',
            "```",
            "",
        ]

    lines += ["## Companies", "", "| Name | ID |", "| --- | --- |"]
    lines += [f"| {company.name} | `{company.id}` |" for company in data.companies]
    lines += ["", "## Users", "", "| Name | Role | ID | Company ID |", "| --- | --- | --- | --- |"]
    lines += [
        f"| {user.name} | {user.role} | `{user.id}` | `{user.company_id}` |" for user in data.users
    ]
    return "\n".join(lines) + "\n"


def render_json(
    data: ConnectionData, *, ports: StackPorts, project: str, generated_at: datetime
) -> str:
    """Render the machine-readable connection sheet.

    Args:
        data: Database contents.
        ports: The stack's published host ports.
        project: The Compose project name.
        generated_at: When the sheet was produced.

    Returns:
        JSON text.
    """
    payload = {
        "project": project,
        "generated_at": generated_at.isoformat(),
        "origin": data.origin,
        "api_url": f"{HOST_URL}:{ports.api}",
        "api_url_from_container": f"{DOCKER_URL}:{ports.api}",
        "ports": asdict(ports),
        "developers": [asdict(developer) for developer in data.developers],
        "companies": [asdict(company) for company in data.companies],
        "users": [asdict(user) for user in data.users],
    }
    return json.dumps(payload, indent=2, default=str) + "\n"


def _write_files(*, data: ConnectionData, ports: StackPorts, project: str) -> None:
    # Both files embed raw API keys
    generated_at = datetime.now(tz=UTC)
    write_private(
        SHEET_DIR / "connection.md",
        render_markdown(data, ports=ports, project=project, generated_at=generated_at),
    )
    write_private(
        SHEET_DIR / "connection.json",
        render_json(data, ports=ports, project=project, generated_at=generated_at),
    )


async def _write_sheet(*, origin: str, ports: StackPorts, project: str) -> None:
    data = await gather_connection(keys=load_keys(), origin=origin)
    _write_files(data=data, ports=ports, project=project)


@click.command(help="Write .dev/connection.md and .dev/connection.json for this stack.")
@click.option("--origin", required=True, type=click.Choice(["copied-from-main", "populated"]))
@click.option("--ports-json", required=True, help="JSON of StackPorts field names to ints.")
@click.option("--project", required=True, help="Compose project name of this stack.")
def main(*, origin: str, ports_json: str, project: str) -> None:
    """Entry point for `python -m scripts.devenv.connection`."""
    ports = StackPorts(**json.loads(ports_json))
    run_with_tortoise(_write_sheet(origin=origin, ports=ports, project=project))


if __name__ == "__main__":
    main()
