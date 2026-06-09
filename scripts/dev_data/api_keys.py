"""API-key reporting for generated dev developers, including permission tiers."""

from dataclasses import dataclass, field
from uuid import UUID

from rich.console import Console

from vapi.cli.constants import API_KEYS_FILE, DEV_FOLDER

_console = Console()


@dataclass
class DevApiKey:
    """A generated developer's API key plus the access tier it grants."""

    api_key: str
    developer_id: UUID
    username: str
    email: str
    is_global_admin: bool
    # (company_id, CompanyPermission value) pairs; empty for the global admin.
    company_permissions: list[tuple[UUID, str]] = field(default_factory=list)

    def access_lines(self) -> list[str]:
        """Generate formatted access lines describing the key's permission tiers."""
        if self.is_global_admin:
            return ["Access:          GLOBAL ADMIN (implicit access to all companies)"]
        if not self.company_permissions:
            return ["Access:          (none)"]
        return [
            f"Access:          {company_id}: {permission}"
            for company_id, permission in self.company_permissions
        ]


def write_api_keys_to_stdout(keys: list[DevApiKey]) -> None:
    """Print every generated developer's key and access tier to the console."""
    _console.rule("API Keys")
    _console.print("[bold red]Save these API keys, they will not be displayed again.[/bold red]")
    for key in keys:
        _console.print(f"[underline]id:              {key.developer_id}")
        _console.print(f"Name:            {key.username}")
        _console.print(f"Email:           {key.email}")
        _console.print(f"API key:         [green bold]{key.api_key}[/green bold]")
        _console.print(f"Is global admin: {key.is_global_admin}")
        for line in key.access_lines():
            _console.print(line)
        _console.print()


def write_api_keys_to_file(keys: list[DevApiKey]) -> None:
    """Write every generated developer's key and access tier to the dev keys file."""
    DEV_FOLDER.mkdir(parents=True, exist_ok=True)
    with API_KEYS_FILE.open("w") as f:
        for key in keys:
            access = "\n".join(key.access_lines())
            f.write(
                f"id:              {key.developer_id}\n"
                f"Name:            {key.username}\n"
                f"Email:           {key.email}\n"
                f"API key:         {key.api_key}\n"
                f"Is global admin: {key.is_global_admin}\n"
                f"{access}\n\n"
            )
    _console.print(f"API keys saved to [green bold]{API_KEYS_FILE}[/green bold]\n")
