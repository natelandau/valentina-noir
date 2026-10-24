"""Duty tasks for the project."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from duty import duty
from rich.console import Console

if TYPE_CHECKING:
    from duty.context import Context


console = Console()
PROJECT_ROOT = Path(__file__).parent
PY_SRC_LIST = tuple(_ for _ in ("src/", "tests/", "duties.py", "scripts/") if Path(_).exists())
# Matches gate-cache: CI is on unless unset, empty, "0", or "false"
CI = os.environ.get("CI", "").strip().lower() not in {"", "0", "false"}
ENV_FILE = PROJECT_ROOT / ".env.secret"
# Holds only disposable output; container data under .dev/ (postgres, redis) must survive cleaning
DEV_DIRECTORIES = [PROJECT_ROOT / ".dev" / "logs"]
# Directories never descended into when cleaning, so a sweep skips the virtualenv and git internals
CLEAN_SKIP_DIRS = {".venv", ".git", ".dev", "node_modules"}


def compose(*args: str) -> list[str]:
    """Build a `docker compose` command for the local PostgreSQL and Redis containers.

    Compose interpolates `${VAR}` from `.env` only, so pass `.env.secret` when it exists to pick
    up settings such as `VAPI_POSTGRES__PORT`.

    Args:
        *args: Compose subcommand and its arguments.

    Returns:
        list[str]: The full command.
    """
    env_args = ["--env-file", str(ENV_FILE)] if ENV_FILE.exists() else []
    return ["docker", "compose", *env_args, "-f", "compose-db.yml", *args]


def gated(name: str, cmd: list[str]) -> list[str]:
    """Wrap a gate command in gate-cache so it skips on a tree where it already passed.

    Args:
        name (str): Marker name for the gate.
        cmd (list[str]): Command to run.

    Returns:
        list[str]: The command prefixed with the gate-cache invocation.
    """
    return ["gate-cache", "--name", name, "--", *cmd]


def ensure_dev_dirs() -> None:
    """Create the local development directories the app writes into."""
    for directory in DEV_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)


def remove(path: Path) -> None:
    """Delete a file or directory tree, ignoring paths that are already gone.

    Args:
        path (Path): File or directory to delete.
    """
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


@duty()
def dev_clean(ctx: Context) -> None:  # noqa: ARG001
    """Delete local development logs."""
    for directory in DEV_DIRECTORIES:
        if directory.exists():
            shutil.rmtree(directory)
            console.print(f"✓ Cleaned dev env in '{directory.name}/'")


@duty(post=[dev_clean])
def clean(ctx: Context) -> None:  # noqa: ARG001
    """Remove build artifacts, coverage reports, caches, and stray OS files."""
    for pattern in (".coverage*", "coverage.xml", ".cache", "build", "dist", "*.log"):
        for path in PROJECT_ROOT.glob(pattern):
            remove(path)

    for root, dirs, files in PROJECT_ROOT.walk():
        dirs[:] = [d for d in dirs if d not in CLEAN_SKIP_DIRS]
        if "__pycache__" in dirs:
            remove(root / "__pycache__")
            dirs.remove("__pycache__")
        if ".DS_Store" in files:
            remove(root / ".DS_Store")
    console.print("✓ Cleaned project artifacts")


@duty
def ruff(ctx: Context) -> None:
    """Check the code quality with ruff."""
    ctx.run(
        gated("ruff", ["ruff", "check", "--config", "pyproject.toml", "--no-fix", *PY_SRC_LIST]),
        title="code quality check",
    )


@duty
def format(ctx: Context) -> None:  # noqa: A001
    """Check the code formatting with ruff."""
    ctx.run(
        gated("format", ["ruff", "format", "--check", "--config", "pyproject.toml", *PY_SRC_LIST]),
        title="code formatting",
    )


@duty
def ty(ctx: Context) -> None:
    """Type check the code with ty."""
    ctx.run(gated("ty", ["ty", "check"]), title="ty check")


@duty
def typos(ctx: Context) -> None:
    """Check the code with typos."""
    ctx.run(gated("typos", ["typos", "--config", ".typos.toml"]), title="typos check")


@duty(skip_if=CI, skip_reason="skip prek in CI environments")
def precommit(ctx: Context) -> None:
    """Run prek hooks."""
    ctx.run(
        # Skip the hooks that call the duties above; lint runs those directly
        "PREK_SKIP=pytest,ruff,format,ty,typos gate-cache --name prek -- prek run --all-files",
        title="prek hooks",
    )


@duty(pre=[ruff, format, ty, typos, precommit], capture=CI)
def lint(ctx: Context) -> None:
    """Run all linting duties."""


@duty
def fix(ctx: Context) -> None:
    """Apply ruff's autofixes and formatting so lint has less to complain about."""
    ctx.run(
        ["ruff", "check", "--config", "pyproject.toml", "--fix", *PY_SRC_LIST], title="ruff fix"
    )
    ctx.run(["ruff", "format", "--config", "pyproject.toml", *PY_SRC_LIST], title="ruff format")


@duty()
def update_dockerfile(ctx: Context) -> None:
    """Pin the Dockerfile's uv image to the locally installed uv version."""
    dockerfile = PROJECT_ROOT / "Dockerfile"
    version_output = ctx.run(["uv", "--version"], title="uv version", capture=True)
    match = re.search(r"(\d+\.\d+\.\d+)", version_output)
    if match is None:
        msg = f"Could not parse uv version from output: {version_output!r}"
        raise RuntimeError(msg)
    version = match.group(1)
    dockerfile_content = dockerfile.read_text(encoding="utf-8")
    if not re.search(rf"uv:{re.escape(version)}\b", dockerfile_content):
        dockerfile_content = re.sub(r"uv:\d+\.\d+\.\d+", f"uv:{version}", dockerfile_content)
        dockerfile.write_text(dockerfile_content, encoding="utf-8")
        console.print(
            f"[green]✓[/green] [bold]Dockerfile updated with uv version: {version}[/bold]"
        )


@duty(capture=CI, post=[update_dockerfile])
def update(ctx: Context) -> None:
    """Upgrade dependencies and prek hooks."""
    ctx.run(["uv", "lock", "--upgrade"], title="update uv lock")
    ctx.run(["uv", "sync"], title="update uv sync")
    ctx.run(["prek", "autoupdate"], title="prek autoupdate")
    ctx.run(["uvx", "uv-upx", "upgrade", "run"], title="uv-upx upgrade")


@duty()
def test(ctx: Context, *cli_args: str) -> None:
    """Test package and generate coverage reports."""
    ctx.run("docker info", title="Run `docker info` to check if docker is running")

    cmd = [
        "pytest",
        "tests/",
        "-c",
        "pyproject.toml",
        "--color=yes",
        "--cov",
        "--cov-config=pyproject.toml",
        "--cov-report=xml",
        "--cov-report=term",
        *cli_args,
    ]
    # A marker covers the name, not the arguments, so a filtered pass must not skip the full suite
    ctx.run(
        cmd if cli_args else gated("test", cmd),
        title="Running tests - this may take a while",
        capture=CI,
    )


@duty(pre=[lint, test])
def check(ctx: Context) -> None:
    """Run the linters and the full test suite, the same gates the pre-push hook runs."""


@duty()
def docs(ctx: Context, addr: str = "localhost:8100") -> None:
    """Serve the documentation site with live reload.

    Args:
        ctx: The duty context.
        addr: Address and port to serve on. Defaults off port 8000 so it can run beside the API.
    """
    ctx.run(
        ["uv", "run", "--group", "docs", "zensical", "serve", "--dev-addr", addr],
        title=f"serve docs at http://{addr}",
        capture=False,
    )


@duty()
def db_up(ctx: Context) -> None:
    """Start the PostgreSQL and Redis containers if they are not already running."""
    ctx.run(compose("up", "-d", "--wait"), title="start database containers")


@duty()
def db_down(ctx: Context) -> None:
    """Stop the PostgreSQL and Redis containers, keeping their data."""
    ctx.run(compose("stop"), title="stop database containers")


@duty()
def db_logs(ctx: Context) -> None:
    """Follow the PostgreSQL and Redis container logs."""
    ctx.run(compose("logs", "--follow", "--tail", "100"), title="database logs", capture=False)


@duty(pre=[db_up])
def psql(ctx: Context) -> None:
    """Open a psql shell in the PostgreSQL container."""
    ctx.run(
        compose("exec", "postgres", "psql", "-U", "valentina", "-d", "valentina-noir"),
        title="psql",
        capture=False,
    )


@duty(pre=[db_up])
def redis_cli(ctx: Context) -> None:
    """Open a redis-cli shell in the Redis container."""
    ctx.run(
        compose("exec", "redis", "redis-cli", "-a", "redispassword", "--no-auth-warning"),
        title="redis-cli",
        capture=False,
    )


@duty(pre=[db_up])
def migrate(ctx: Context) -> None:
    """Apply pending database migrations."""
    ctx.run("uv run app migrate", title="apply database migrations", capture=False)


@duty(pre=[db_up])
def makemigrations(ctx: Context) -> None:
    """Generate migration files from model changes."""
    ctx.run("uv run app makemigrations", title="generate database migrations", capture=False)


@duty(pre=[db_up])
def seed(ctx: Context) -> None:
    """Seed the database with reference data."""
    ctx.run("uv run app seed", title="seed development database", capture=False)


@duty(pre=[db_up])
def populate(ctx: Context) -> None:
    """Reset and populate the development database with varied test data."""
    ctx.run(
        "uv run python -m scripts.populate_dev_db",
        title="populate development database",
        capture=False,
    )


@duty(pre=[db_up])
def reset(ctx: Context) -> None:
    """Drop, recreate, and seed the development database without test data."""
    ctx.run(
        "uv run python -m scripts.populate_dev_db --reset-only",
        title="reset development database",
        capture=False,
    )


@duty()
def dev_setup(ctx: Context) -> None:
    """Install dependencies and git hooks, then prepare the local database."""
    ctx.run(["uv", "sync", "--all-groups"], title="install dependencies")
    ctx.run(["prek", "install"], title="install git hooks")
    ensure_dev_dirs()

    if not ENV_FILE.exists():
        shutil.copyfile(PROJECT_ROOT / ".env.example", ENV_FILE)
        console.print(
            f"""
[yellow]Created {ENV_FILE.name} from .env.example.[/yellow]
  Fill in the required values (see CONTRIBUTING.md), then run [green]duty dev-setup[/green] again.
"""
        )
        return

    migrate(ctx)
    seed(ctx)
    console.print(
        """
✓ Development environment setup complete.

  Run the API locally:          [green]duty run[/green]
  Fill the database with data:  [green]duty populate[/green]
  Run the full stack in Docker: [green]duty stack[/green]
"""
    )


@duty(pre=[migrate])
def run(ctx: Context) -> None:
    """Run the application locally in development mode."""
    ensure_dev_dirs()
    ctx.run("uv run app run -r --reload-paths=src/", title="run application locally", capture=False)


@duty()
def stack(ctx: Context) -> None:
    """Build and start the full application stack (API, PostgreSQL, Redis) in Docker."""
    # Always --build: a plain `docker compose up` reuses the cached image and can serve
    # stale code against a database whose schema has moved on, breaking startup migrations/seed.
    ctx.run("docker compose up --build", title="build and start full docker stack", capture=False)
