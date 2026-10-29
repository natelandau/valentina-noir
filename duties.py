"""Duty tasks for the project."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from duty import duty
from rich.console import Console

if TYPE_CHECKING:
    from collections.abc import Callable

    from duty.context import Context


console = Console()
PROJECT_ROOT = Path(__file__).parent.resolve()
# duty loads this file by path, so the project root is not importable until added
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.devenv import stack as devstack  # noqa: E402
from scripts.devenv import worktrees  # noqa: E402
from scripts.devenv.compose import StackError  # noqa: E402
from scripts.devenv.registry import RegistryFormatError, SlotConflictError  # noqa: E402


def _main_checkout() -> Path:
    """Return the main checkout, which is PROJECT_ROOT unless this file runs from a worktree."""
    result = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],  # noqa: S607
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return Path(result.stdout.strip()).parent.resolve() if result.returncode == 0 else PROJECT_ROOT


MAIN_ROOT = _main_checkout()
IN_WORKTREE = PROJECT_ROOT != MAIN_ROOT
PY_SRC_LIST = tuple(_ for _ in ("src/", "tests/", "duties.py", "scripts/") if Path(_).exists())
# Matches gate-cache: CI is on unless unset, empty, "0", or "false"
CI = os.environ.get("CI", "").strip().lower() not in {"", "0", "false"}
_GATE_CACHE_DISABLE = os.environ.get("GATE_CACHE_DISABLE", "").strip().lower()
# Matches gate-cache: GATE_CACHE_DISABLE decides when set, otherwise CI does
GATE_CACHE_ON = _GATE_CACHE_DISABLE in {"0", "false"} or (not _GATE_CACHE_DISABLE and not CI)
# Holds only disposable output; the rest of .dev/ (keys, generated secrets) must survive cleaning
DEV_DIRECTORIES = [PROJECT_ROOT / ".dev" / "logs"]
# Directories never descended into when cleaning, so a sweep skips the virtualenv, git internals,
# and other worktrees
CLEAN_SKIP_DIRS = {".venv", ".git", ".dev", ".worktrees", "node_modules"}


def gated(name: str, cmd: list[str]) -> list[str]:
    """Wrap a gate command in gate-cache so it skips on a tree where it already passed.

    Args:
        name (str): Marker name for the gate.
        cmd (list[str]): Command to run.

    Returns:
        list[str]: The command prefixed with the gate-cache invocation.
    """
    return ["gate-cache", "--name", name, "--", *cmd]


def gate_passed(name: str) -> bool:
    """Report whether a gate would skip because it already passed on the current tree.

    Use it to avoid setup, such as starting servers, that only a gate that runs needs.

    Args:
        name (str): Marker name for the gate.

    Returns:
        bool: True when gate-cache is on and holds a pass for this tree.
    """
    if not GATE_CACHE_ON:
        return False
    try:
        result = subprocess.run(  # noqa: S603
            ["gate-cache", "status", "--name", name],  # noqa: S607
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


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
    """Start this checkout's test servers, then test the package and generate coverage reports."""
    # A cached pass skips pytest, so a push on a tested tree needs neither Docker nor the servers
    if cli_args or not gate_passed("test"):
        ctx.run("docker info", title="Run `docker info` to check if docker is running")
        # pytest inherits the environment, which points it at this checkout's slot
        os.environ.update(
            devstack.run_task(devstack.start_test_services, cwd=PROJECT_ROOT, claim=True)
        )

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
def up(ctx: Context, debug: bool = False) -> None:  # noqa: ARG001, FBT001, FBT002
    """Build and start this checkout's stack, fill an empty database, migrate, and register it.

    Args:
        ctx: The duty context.
        debug: Start the API under debugpy instead of the auto-reloading server.
    """
    devstack.run_task(lambda stack: devstack.up(stack, debug=debug), cwd=PROJECT_ROOT, claim=True)


@duty()
def down(ctx: Context) -> None:  # noqa: ARG001
    """Stop this checkout's stack, keeping its data."""
    devstack.run_task(devstack.down, cwd=PROJECT_ROOT)


@duty()
def reset(ctx: Context, debug: bool = False, fresh: bool = False) -> None:  # noqa: ARG001, FBT001, FBT002
    """Delete this checkout's stack data and rebuild it, after a confirmation prompt.

    Args:
        ctx: The duty context.
        debug: Start the rebuilt API under debugpy, as `up debug=true` does.
        fresh: In a worktree, rebuild from populate with new IDs and keys instead of recopying
            main. Main always rebuilds from populate.
    """
    devstack.run_task(
        lambda stack: devstack.reset(stack, debug=debug, fresh=fresh), cwd=PROJECT_ROOT, claim=True
    )


@duty()
def logs(ctx: Context) -> None:  # noqa: ARG001
    """Follow this checkout's stack logs."""
    devstack.run_task(devstack.logs, cwd=PROJECT_ROOT)


@duty()
def info(ctx: Context) -> None:  # noqa: ARG001
    """Print this checkout's connection sheet."""
    devstack.run_task(devstack.info, cwd=PROJECT_ROOT)


@duty()
def envs(ctx: Context) -> None:  # noqa: ARG001
    """List every registered stack on this machine."""
    _registry_task(devstack.envs)


@duty()
def psql(ctx: Context) -> None:  # noqa: ARG001
    """Open a psql shell on this checkout's database."""
    devstack.run_task(devstack.psql, cwd=PROJECT_ROOT)


@duty()
def redis_cli(ctx: Context) -> None:  # noqa: ARG001
    """Open a redis-cli shell on this checkout's Redis."""
    devstack.run_task(devstack.redis_cli, cwd=PROJECT_ROOT)


@duty()
def migrate(ctx: Context) -> None:  # noqa: ARG001
    """Apply pending database migrations, then seed reference data."""
    devstack.run_task(lambda stack: devstack.app_command(stack, "migrate"), cwd=PROJECT_ROOT)


@duty()
def makemigrations(ctx: Context) -> None:  # noqa: ARG001
    """Generate migration files from model changes."""
    devstack.run_task(lambda stack: devstack.app_command(stack, "makemigrations"), cwd=PROJECT_ROOT)


@duty()
def seed(ctx: Context) -> None:  # noqa: ARG001
    """Seed the database with reference data."""
    devstack.run_task(lambda stack: devstack.app_command(stack, "seed"), cwd=PROJECT_ROOT)


@duty()
def populate(ctx: Context, *cli_args: str) -> None:  # noqa: ARG001
    """Replace this checkout's data with varied test data and new keys, after a prompt.

    Args:
        ctx: The duty context.
        *cli_args: Options for `scripts.populate_dev_db` after `--`, such as `-- --companies 3`.
    """
    devstack.run_task(lambda stack: devstack.populate(stack, *cli_args), cwd=PROJECT_ROOT)


@duty()
def developer(ctx: Context, username: str, email: str, admin: bool = False) -> None:  # noqa: ARG001, FBT001, FBT002
    """Create a developer in this checkout's database and record its API key.

    Args:
        ctx: The duty context.
        username: The developer's username.
        email: The developer's email.
        admin: Make the developer a global admin.
    """
    devstack.run_task(
        lambda stack: devstack.developer(stack, username=username, email=email, admin=admin),
        cwd=PROJECT_ROOT,
    )


@duty()
def dev_setup(ctx: Context) -> None:
    """Install dependencies and git hooks."""
    ctx.run(["uv", "sync", "--all-groups"], title="install dependencies")
    ctx.run(["prek", "install"], title="install git hooks")
    console.print(
        """
✓ Development environment setup complete.

  Start this checkout's stack: [green]uv run duty up[/green]
"""
    )


def _registry_task[T](action: Callable[[], T]) -> T:
    """Run an action that needs no checkout stack, turning a failure into a message and exit 1."""
    try:
        return action()
    except (StackError, SlotConflictError) as error:
        console.print(f"[red]{error}[/red]")
        raise SystemExit(1) from error
    except RegistryFormatError as error:
        devstack.report_bad_registry(error)
        raise SystemExit(1) from error
    except FileNotFoundError as error:
        console.print(f"[red]`{error.filename}` was not found. Install it and try again.[/red]")
        raise SystemExit(1) from error


@duty()
def worktree(ctx: Context, branch: str) -> None:  # noqa: ARG001
    """Create .worktrees/<branch> on a new branch with its own stack slot.

    Args:
        ctx: The duty context.
        branch: The new branch, which also names the worktree directory.
    """
    path = _registry_task(lambda: worktrees.create(main=MAIN_ROOT, branch=branch))
    console.print(f"\n[green]✓[/green] Worktree ready. Start it with: cd {path} && uv run duty up")


@duty()
def worktree_teardown(ctx: Context, branch: str = "") -> None:  # noqa: ARG001
    """Remove a worktree, its stack containers and volumes, and its slot; the branch is kept.

    Args:
        ctx: The duty context.
        branch: The worktree's branch. Defaults to the worktree this runs in.
    """
    if branch:
        target = MAIN_ROOT / ".worktrees" / branch
    elif IN_WORKTREE:
        target = PROJECT_ROOT
    else:
        console.print(
            "[red]Name the worktree to remove: duty worktree-teardown branch=<branch>[/red]"
        )
        raise SystemExit(1)
    # The worktree directory may disappear under this process, so leave it for good rather than
    # with ctx.cd, which would change back into the deleted directory afterward
    os.chdir(MAIN_ROOT)
    _registry_task(lambda: worktrees.teardown(main=MAIN_ROOT, target=target))


@duty()
def worktree_prune(ctx: Context) -> None:  # noqa: ARG001
    """Remove the stacks of worktrees that no longer exist."""
    pruned = _registry_task(lambda: worktrees.prune(main=MAIN_ROOT))
    console.print(f"Pruned {len(pruned)} stack(s): {', '.join(pruned) or 'none'}")
