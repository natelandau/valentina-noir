"""Build the environment and command lines for a checkout's Docker Compose stack."""

import os
import secrets
import subprocess
from pathlib import Path

from scripts.devenv.ports import StackPorts

GENERATED_ENV_KEYS = ("VAPI_AUTHENTICATION_ENCRYPTION_KEY", "VAPI_RATE_LIMIT__ENCRYPTION_KEY")
# Mirror the postgres service in compose.yml
POSTGRES_USER = "valentina"
POSTGRES_PASSWORD = "valentina"  # noqa: S105
POSTGRES_DB = "valentina-noir"
# Every published port binds 127.0.0.1; containers reach the host through host.docker.internal
HOST_URL = "http://127.0.0.1"
DOCKER_URL = "http://host.docker.internal"


class StackError(RuntimeError):
    """Raised when a dev stack step fails, with a message meant for the developer."""


def compose_env(*, ports: StackPorts, debug: bool) -> dict[str, str]:
    """Build the environment to run `docker compose` with for one stack.

    Compose interpolates these into `compose.yml`, so the stack publishes its slot's ports and
    the API container runs as the host user, keeping files it writes to bind mounts owned by you.

    Args:
        ports: The stack's host ports.
        debug: Start the API under debugpy instead of the auto-reloading server.

    Returns:
        The current process environment plus the stack's variables.
    """
    return {
        **os.environ,
        **ports.as_env(),
        "VAPI_DEV_UID": str(os.getuid()),
        "VAPI_DEV_GID": str(os.getgid()),
        "VAPI_DEV_DEBUGPY": "1" if debug else "0",
    }


def compose_cmd(*args: str, checkout: Path, project: str) -> list[str]:
    """Build a `docker compose` command pinned to one checkout's project.

    Args:
        *args: The Compose subcommand and its arguments.
        checkout: The checkout whose `compose.yml` defines the stack.
        project: The Compose project name for the checkout.

    Returns:
        The argument list to pass to a subprocess.
    """
    return ["docker", "compose", "--project-directory", str(checkout), "-p", project, *args]


def ensure_generated_env(checkout: Path) -> Path:
    """Create the checkout's generated secrets file unless it already exists.

    The keys encrypt data stored in the stack's database and Redis, so regenerating them would
    strand that data. The file is written once and never overwritten.

    Args:
        checkout: The checkout root.

    Returns:
        The path to `.dev/generated.env`.
    """
    path = checkout / ".dev" / "generated.env"
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={secrets.token_hex(32)}" for key in GENERATED_ENV_KEYS]
    # Create with owner-only permissions so the keys are never readable by others, even briefly
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return path


def is_fresh(*, checkout: Path, project: str) -> bool:
    """Tell whether a running stack's database has never been initialized.

    Decides whether `up` must fill the database (copy from main or populate) before migrating.

    Args:
        checkout: The checkout whose `compose.yml` defines the stack.
        project: The Compose project name for the checkout.

    Returns:
        True when the database has no `developer` table.

    Raises:
        StackError: If the query cannot run, such as when `postgres` is down.
    """
    query = "select to_regclass('public.developer')"
    cmd = compose_cmd(
        "exec",
        "-T",
        "postgres",
        "psql",
        "-U",
        POSTGRES_USER,
        "-d",
        POSTGRES_DB,
        "-tAc",
        query,
        checkout=checkout,
        project=project,
    )
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
    if result.returncode != 0:
        msg = f"Could not query the {project} database: {result.stderr.strip()}"
        raise StackError(msg)
    return not result.stdout.strip()
