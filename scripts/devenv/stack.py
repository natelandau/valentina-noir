"""Lifecycle of one checkout's dev stack: the orchestration behind the stack duties.

Host code here only drives Compose, files, and the registry. Anything that touches the stack's
database runs inside the `api` container.
"""

import contextlib
import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table

from scripts.devenv.compose import (
    DOCKER_URL,
    HOST_URL,
    POSTGRES_DB,
    POSTGRES_USER,
    StackError,
    compose_cmd,
    compose_env,
    ensure_generated_env,
    is_fresh,
)
from scripts.devenv.copy import MainNotInitializedError, copy_from_main
from scripts.devenv.ports import StackPorts, project_name
from scripts.devenv.registry import (
    MAIN_KEY,
    Environment,
    Registry,
    RegistryFormatError,
    SlotConflictError,
    registry_path,
)
from scripts.devenv.s3 import BUCKET, ensure_bucket

console = Console()
ORIGIN_COPIED = "copied-from-main"
ORIGIN_POPULATED = "populated"
TEST_SERVICES_HOST = "127.0.0.1"
POPULATE = ("python", "-m", "scripts.populate_dev_db", "--yes")
_PUBLISHED_PORT = re.compile(r":(\d+)(?:-(\d+))?->")


class PortInUseError(StackError):
    """Raised when a port the stack publishes is held by something outside the stack."""

    def __init__(self, port: int, holder: str) -> None:
        self.port = port
        self.holder = holder
        super().__init__(
            f"Port {port} is in use by {holder}. Stop it, then run `uv run duty up` again."
        )


def run_git(cwd: Path, *args: str) -> str:
    """Run git in `cwd` and return its stripped output.

    Raises:
        StackError: If git exits non-zero.
    """
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        msg = f"`git {' '.join(args)}` failed in {cwd}: {result.stderr.strip()}"
        raise StackError(msg)
    return result.stdout.strip()


def main_checkout(cwd: Path) -> Path:
    """Return the main checkout of the repository `cwd` belongs to.

    Args:
        cwd: Any directory inside the main checkout or one of its worktrees.

    Returns:
        The parent of the shared git directory.
    """
    common = run_git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(common).parent.resolve()


def checkout_identity(cwd: Path) -> tuple[Path, str | None]:
    """Identify the checkout a command runs in.

    Args:
        cwd: Any directory inside the checkout.

    Returns:
        The checkout root, and its branch, or `None` for the main checkout.

    Raises:
        StackError: If a worktree has no branch checked out.
    """
    root = Path(run_git(cwd, "rev-parse", "--show-toplevel")).resolve()
    if root == main_checkout(cwd):
        return root, None
    branch = run_git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if branch == "HEAD":
        msg = f"{root} has a detached HEAD; check out a branch so its stack has a name"
        raise StackError(msg)
    return root, branch


@dataclass(frozen=True)
class Stack:
    """One checkout's stack: where it lives, what it is called, and its slot."""

    checkout: Path
    branch: str | None
    main: Path
    slot: int

    @property
    def is_main(self) -> bool:
        """Whether this is the main checkout's stack."""
        return self.branch is None

    @property
    def key(self) -> str:
        """Registry key: the branch, or `main`."""
        return self.branch or MAIN_KEY

    @property
    def project(self) -> str:
        """Compose project name."""
        return project_name(branch=self.branch)

    @property
    def ports(self) -> StackPorts:
        """Host ports of the slot."""
        return StackPorts.for_slot(self.slot)

    @property
    def dev_dir(self) -> Path:
        """The checkout's gitignored `.dev` directory, bind-mounted into `api`."""
        return self.checkout / ".dev"

    @property
    def api_url(self) -> str:
        """API base URL on the host."""
        return f"{HOST_URL}:{self.ports.api}"

    def environment(self, developers: list[dict[str, Any]]) -> Environment:
        """Build the stack's registry entry.

        Args:
            developers: Developers from the connection sheet.

        Returns:
            The entry to upsert.
        """
        return Environment(
            key=self.key,
            checkout=self.checkout,
            branch=self.key,
            slot=self.slot,
            project=self.project,
            ports=self.ports,
            api_url=self.api_url,
            api_url_from_containers=f"{DOCKER_URL}:{self.ports.api}",
            healthz_url=f"{self.api_url}/healthz",
            connection_sheet=self.dev_dir / "connection.md",
            keys_file=self.dev_dir / "api-keys.json",
            developers=developers,
        )


def claim_stack(cwd: Path) -> Stack:
    """Resolve the checkout's stack, reserving a slot and registering it when new.

    Args:
        cwd: Any directory inside the checkout.

    Returns:
        The stack.
    """
    checkout, branch = checkout_identity(cwd)
    main = main_checkout(cwd)
    with Registry.locked() as registry:
        slot = registry.assign_slot(key=branch or MAIN_KEY, checkout=checkout)
        stack = Stack(checkout=checkout, branch=branch, main=main, slot=slot)
        existing = registry.entries().get(stack.key)
        registry.upsert(stack.environment(existing.developers if existing else []))
    return stack


def load_stack(cwd: Path) -> Stack:
    """Resolve the checkout's stack without claiming a slot.

    Args:
        cwd: Any directory inside the checkout.

    Returns:
        The stack.

    Raises:
        StackError: If the checkout has never been started.
    """
    checkout, branch = checkout_identity(cwd)
    slot = Registry.load().claimed_slot(branch or MAIN_KEY)
    if slot is None:
        msg = "This checkout has no stack yet. Start it with `uv run duty up`."
        raise StackError(msg)
    return Stack(checkout=checkout, branch=branch, main=main_checkout(cwd), slot=slot)


def report_bad_registry(error: Exception) -> None:
    """Tell the developer the registry file cannot be read and how to recover.

    Args:
        error: The failure from reading the registry.
    """
    console.print(
        f"[red]Could not read the dev stack registry at {registry_path()} ({error}); fix or "
        "delete it. `uv run duty up` in each checkout registers its stack again.[/red]",
        soft_wrap=True,
    )


def run_task[T](action: Callable[[Stack], T], *, cwd: Path, claim: bool = False) -> T:
    """Run a stack action for the checkout at `cwd`, turning failures into a message and exit 1.

    Args:
        action: The action, called with the checkout's stack.
        cwd: Any directory inside the checkout.
        claim: Reserve a slot and register the checkout when it has none, as `up` must.
            Otherwise a checkout that was never started fails with a pointer to `up`.

    Returns:
        What the action returns.
    """
    try:
        return action(claim_stack(cwd) if claim else load_stack(cwd))
    except (StackError, SlotConflictError, BotoCoreError, ClientError) as error:
        console.print(f"[red]{error}[/red]")
        raise SystemExit(1) from error
    except RegistryFormatError as error:
        report_bad_registry(error)
        raise SystemExit(1) from error
    except FileNotFoundError as error:
        console.print(f"[red]`{error.filename}` was not found. Install it and try again.[/red]")
        raise SystemExit(1) from error


def _compose(
    stack: Stack, *args: str, debug: bool = False, check: bool = True, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    cmd = compose_cmd(*args, checkout=stack.checkout, project=stack.project)
    result = subprocess.run(  # noqa: S603
        cmd,
        env=compose_env(ports=stack.ports, debug=debug),
        capture_output=capture,
        text=True,
        check=False,
    )
    if check and result.returncode != 0:
        msg = f"`docker compose {' '.join(args)}` failed for {stack.project} (exit {result.returncode})"
        raise StackError(msg)
    return result


def _require_running(stack: Stack, service: str) -> None:
    result = _compose(stack, "ps", "--status", "running", "-q", service, check=False, capture=True)
    if result.returncode != 0 or not result.stdout.strip():
        msg = f"{service} is not running for this checkout. Start it with `uv run duty up`."
        raise StackError(msg)


def _own_published_ports(project: str) -> set[int]:
    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "docker",
            "ps",
            "--filter",
            f"label=com.docker.compose.project={project}",
            "--format",
            "{{.Ports}}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    ports: set[int] = set()
    for match in _PUBLISHED_PORT.finditer(result.stdout):
        first = int(match.group(1))
        last = int(match.group(2) or first)
        ports.update(range(first, last + 1))
    return ports


def _container_on(port: int) -> str:
    result = subprocess.run(  # noqa: S603
        ["docker", "ps", "--filter", f"publish={port}", "--format", "{{.Names}}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return ", ".join(result.stdout.split())


def _port_holder(port: int) -> str | None:
    result = subprocess.run(  # noqa: S603
        # Field output (`p<pid>`, `c<command>`) keeps full command names, spaces included
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-Fpc"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    fields = {line[0]: line[1:] for line in reversed(result.stdout.splitlines()) if line}
    if "p" not in fields:
        return None
    holder = f"{fields.get('c', 'unknown')} (pid {fields['p']})"
    container = _container_on(port)
    return f"{holder}, container {container}" if container else holder


def preflight_ports(ports: StackPorts, *, project: str) -> None:
    """Fail before starting anything when a port the stack needs is taken by someone else.

    Docker's own error for a taken port does not say who holds it.

    Args:
        ports: The stack's host ports.
        project: The stack's Compose project; ports its containers publish are fine.

    Raises:
        PortInUseError: If another process or container listens on one of the ports.
    """
    own = _own_published_ports(project)
    for port in asdict(ports).values():
        if port in own:
            continue
        holder = _port_holder(port)
        if holder is not None:
            raise PortInUseError(port, holder)


def _origin_file(stack: Stack) -> Path:
    return stack.dev_dir / "origin"


def _origin(stack: Stack) -> str:
    path = _origin_file(stack)
    if path.exists():
        return path.read_text().strip()
    return ORIGIN_POPULATED if stack.is_main else ORIGIN_COPIED


def _write_sheet(stack: Stack) -> None:
    _compose(
        stack,
        "exec",
        "-T",
        "api",
        "python",
        "-m",
        "scripts.devenv.connection",
        "--origin",
        _origin(stack),
        "--ports-json",
        json.dumps(asdict(stack.ports)),
        "--project",
        stack.project,
    )


def _register(stack: Stack) -> None:
    sheet = stack.dev_dir / "connection.json"
    developers = json.loads(sheet.read_text()).get("developers", []) if sheet.exists() else []
    with Registry.locked() as registry:
        registry.upsert(stack.environment(developers))


def _initialize(stack: Stack, *, debug: bool, fresh: bool) -> None:
    """Fill a stack whose database is empty: populate on main or when asked, else copy main.

    Raises:
        StackError: If filling fails. The stack's volumes are removed first, because a
            partly filled database looks initialized to the next `up` but has no matching keys.
    """
    populating = stack.is_main or fresh
    try:
        if populating:
            _compose(stack, "run", "--rm", "api", *POPULATE, debug=debug)
        else:
            copy_from_main(main=stack.main, target=stack.checkout, target_project=stack.project)
    except MainNotInitializedError:
        raise
    except KeyboardInterrupt:
        _compose(stack, "--profile", "test", "down", "-v", check=False)
        console.print("[yellow]Interrupted; the half-made stack was removed.[/yellow]")
        raise
    except (StackError, BotoCoreError, ClientError, OSError) as error:
        _compose(stack, "--profile", "test", "down", "-v", check=False)
        step = "Populating the database" if populating else "Copying main's data"
        msg = (
            f"{step} failed: {error}. The half-made stack was removed; run `uv run duty up` again."
        )
        raise StackError(msg) from error
    origin = ORIGIN_POPULATED if populating else ORIGIN_COPIED
    _origin_file(stack).write_text(f"{origin}\n")


def up(stack: Stack, *, debug: bool = False, fresh: bool = False) -> None:
    """Build and start the stack, fill an empty database, migrate, and refresh the sheet.

    Args:
        stack: The stack.
        debug: Start the API under debugpy.
        fresh: Populate an empty database even in a worktree, instead of copying main's.
    """
    preflight_ports(stack.ports, project=stack.project)
    # Creates .dev/ as the developer before Compose can create it as root for the bind mount
    ensure_generated_env(stack.checkout)
    _compose(stack, "up", "-d", "--build", "--wait", "postgres", "redis", "s3", debug=debug)
    # `run` reuses an existing image, so build now or a stale image migrates the database
    _compose(stack, "build", "api", debug=debug)
    ensure_bucket(endpoint=f"{HOST_URL}:{stack.ports.s3}", bucket=BUCKET)

    if is_fresh(checkout=stack.checkout, project=stack.project):
        _initialize(stack, debug=debug, fresh=fresh)

    migration = _compose(stack, "run", "--rm", "api", "app", "migrate", debug=debug, check=False)
    if migration.returncode != 0:
        console.print("[red]Database migrations failed.[/red]")
        if _origin(stack) == ORIGIN_COPIED:
            console.print(
                "This stack's data was copied from main. If main's data is ahead of this "
                "branch's migrations, rebuild it from scratch with: "
                "[green]uv run duty reset fresh=true[/green]"
            )
        raise SystemExit(1)

    _compose(stack, "up", "-d", "--wait", "api", debug=debug)
    _write_sheet(stack)
    _register(stack)
    console.print(
        f"\n[green]✓[/green] {stack.project} is up\n"
        f"  API:              {stack.api_url}\n"
        f"  Connection sheet: {stack.dev_dir / 'connection.md'}",
        soft_wrap=True,
    )


def down(stack: Stack) -> None:
    """Stop the stack and keep its data volumes."""
    _compose(stack, "--profile", "test", "down")


def reset(stack: Stack, *, debug: bool = False, fresh: bool = False) -> None:
    """Delete the stack's data and rebuild it.

    Args:
        stack: The stack.
        debug: Start the rebuilt API under debugpy, as `up` does.
        fresh: In a worktree, rebuild from populate with new IDs and keys instead of recopying
            main. Main always rebuilds from populate.
    """
    source = "populate" if stack.is_main or fresh else "a new copy of main"
    if not Confirm.ask(f"Delete all data in {stack.project} and rebuild it from {source}?"):
        console.print("Aborting...")
        return
    _compose(stack, "--profile", "test", "down", "-v")
    up(stack, debug=debug, fresh=fresh)


def logs(stack: Stack) -> None:
    """Follow the stack's logs until interrupted."""
    with contextlib.suppress(KeyboardInterrupt):
        _compose(stack, "logs", "--follow", "--tail", "100", check=False)


def start_test_services(stack: Stack) -> dict[str, str]:
    """Start the stack's PostgreSQL and Redis test servers for pytest.

    The servers are left running: they hold nothing between runs and the next run reuses them.

    Args:
        stack: The stack.

    Returns:
        The variables that point the test suite at the servers.
    """
    _compose(stack, "--profile", "test", "up", "-d", "--wait", "postgres-test", "redis-test")
    return {
        "VAPI_TEST_SERVICES_HOST": TEST_SERVICES_HOST,
        "VAPI_TEST_POSTGRES_PORT": str(stack.ports.postgres_test),
        "VAPI_TEST_REDIS_PORT": str(stack.ports.redis_test),
    }


def info(stack: Stack) -> None:
    """Print the stack's connection sheet."""
    sheet = stack.dev_dir / "connection.md"
    if not sheet.exists():
        msg = "No connection sheet yet. Start the stack with `uv run duty up`."
        raise StackError(msg)
    console.print(sheet.read_text(), markup=False, highlight=False, soft_wrap=True)


def psql(stack: Stack) -> None:
    """Open psql on the stack's database."""
    _require_running(stack, "postgres")
    # Interactive: the shell's own exit status is not a failure of this task
    _compose(stack, "exec", "postgres", "psql", "-U", POSTGRES_USER, "-d", POSTGRES_DB, check=False)


def redis_cli(stack: Stack) -> None:
    """Open redis-cli on the stack's Redis."""
    _require_running(stack, "redis")
    _compose(stack, "exec", "redis", "redis-cli", check=False)


def app_command(stack: Stack, *args: str) -> None:
    """Run an `app` CLI command, such as `migrate`, inside the stack's `api` container.

    Args:
        stack: The stack.
        *args: The `app` subcommand and its arguments.
    """
    _require_running(stack, "api")
    _compose(stack, "exec", "api", "app", *args)


def populate(stack: Stack, *options: str) -> None:
    """Replace the stack's data with a freshly populated dataset and new keys.

    Args:
        stack: The stack.
        *options: Extra `scripts.populate_dev_db` options, such as `--companies 3`.
    """
    _require_running(stack, "api")
    if not Confirm.ask(f"Delete all data in {stack.project} and populate it with test data?"):
        console.print("Aborting...")
        return
    _compose(stack, "exec", "api", *POPULATE, *options)
    _origin_file(stack).write_text(f"{ORIGIN_POPULATED}\n")
    _write_sheet(stack)
    _register(stack)


def developer(stack: Stack, *, username: str, email: str, admin: bool = False) -> None:
    """Create a developer, record its key, and refresh the sheet.

    Args:
        stack: The stack.
        username: The developer's username.
        email: The developer's email.
        admin: Make the developer a global admin.
    """
    _require_running(stack, "api")
    args = ["--username", username, "--email", email]
    if admin:
        args.append("--global-admin")
    _compose(stack, "exec", "api", "python", "-m", "scripts.devenv.create_developer", *args)
    _write_sheet(stack)
    _register(stack)


def _running_containers(project: str) -> int:
    result = subprocess.run(  # noqa: S603
        ["docker", "ps", "-q", "--filter", f"label=com.docker.compose.project={project}"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return len(result.stdout.split())


def envs() -> None:
    """List every registered stack on this machine with its slot, URL, and running state."""
    table = Table()
    for column in ("Key", "Slot", "API URL", "State", "Connection sheet"):
        table.add_column(column, overflow="fold")
    for key, env in Registry.load().entries().items():
        running = _running_containers(env.project)
        state = f"running ({running} containers)" if running else "stopped"
        if not env.checkout.exists():
            state = "checkout missing"
        table.add_row(key, str(env.slot), env.api_url, state, str(env.connection_sheet))
    console.print(table)
