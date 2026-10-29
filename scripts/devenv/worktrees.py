"""Create, remove, and prune git worktrees together with their dev stacks."""

import shutil
import subprocess
from pathlib import Path

from rich.console import Console

from scripts.devenv.compose import StackError, compose_cmd, compose_env
from scripts.devenv.ports import StackPorts, project_name
from scripts.devenv.registry import MAIN_KEY, Registry
from scripts.devenv.stack import Stack, checkout_identity, run_git

console = Console()
# Local files a worktree needs that git does not carry
COPIED_FILES = ("CLAUDE.local.md",)


def _copy_local_files(*, main: Path, worktree: Path) -> None:
    for name in COPIED_FILES:
        source = main / name
        if not source.exists():
            continue
        # A branch cut before a file was ignored would otherwise commit it
        ignored = subprocess.run(  # noqa: S603
            ["git", "check-ignore", "-q", name],  # noqa: S607
            cwd=worktree,
            check=False,
        )
        if ignored.returncode != 0:
            console.print(f"[yellow]skipped {name}: this branch does not ignore it[/yellow]")
            continue
        shutil.copyfile(source, worktree / name)
        console.print(f"copied {name}")


def _down_with_volumes(*, checkout: Path, project: str, ports: StackPorts) -> bool:
    """Remove a project's containers and volumes, test services included."""
    result = subprocess.run(  # noqa: S603
        compose_cmd("--profile", "test", "down", "-v", checkout=checkout, project=project),
        env=compose_env(ports=ports, debug=False),
        check=False,
    )
    return result.returncode == 0


def _worktrees(main: Path) -> dict[Path, list[str]]:
    """Map each worktree path to the attribute lines of its `git worktree list` block."""
    listing = run_git(main, "worktree", "list", "--porcelain")
    worktrees: dict[Path, list[str]] = {}
    for block in listing.split("\n\n"):
        lines = block.splitlines()
        if lines and lines[0].startswith("worktree "):
            worktrees[Path(lines[0].removeprefix("worktree ")).resolve()] = lines[1:]
    return worktrees


def create(*, main: Path, branch: str) -> Path:
    """Create `.worktrees/<branch>` on a new branch with its own slot, without starting the stack.

    The branch starts from the main checkout's HEAD.

    Args:
        main: The main checkout.
        branch: The new branch, which also names the worktree directory.

    Returns:
        The new worktree.
    """
    path = main / ".worktrees" / branch
    # Reserve the slot first so a failed reservation leaves no worktree to roll back
    with Registry.locked() as registry:
        claimed_before = registry.claimed_slot(branch) is not None
        slot = registry.assign_slot(key=branch, checkout=path)
        # An existing entry keeps its recorded developers; `up` rewrites it from the sheet
        if not claimed_before:
            registry.upsert(
                Stack(checkout=path, branch=branch, main=main, slot=slot).environment([])
            )
    try:
        run_git(main, "worktree", "add", str(path), "-b", branch)
    except StackError:
        # Release only a claim this call made; an earlier claim is still in use
        if not claimed_before:
            with Registry.locked() as registry:
                registry.remove(branch)
        raise
    console.print(f"created worktree {path} on branch {branch}")
    _copy_local_files(main=main, worktree=path)

    try:
        subprocess.run(["uv", "sync", "--all-groups"], cwd=path, check=True)  # noqa: S607
    except subprocess.CalledProcessError as error:
        msg = f"Installing dependencies failed. Finish with: cd {path} && uv sync --all-groups"
        raise StackError(msg) from error
    console.print(f"[green]✓[/green] slot {slot} reserved; start it with `uv run duty up` there")
    return path


def _find_stack(target: Path) -> tuple[str, str, StackPorts]:
    """Find the registry key, Compose project, and ports of a worktree's stack."""
    entry = next(
        (env for env in Registry.load().entries().values() if env.checkout == target), None
    )
    if entry:
        return entry.key, entry.project, entry.ports
    try:
        _, branch = checkout_identity(target)
    except StackError:
        branch = None
    if not branch:
        msg = f"{target} is not a worktree of this repository (no branch, so no stack to find)"
        raise StackError(msg) from None
    return (
        branch,
        project_name(branch=branch),
        StackPorts.for_slot(Registry.load().claimed_slot(branch) or 1),
    )


def teardown(*, main: Path, target: Path) -> None:
    """Remove a worktree, its stack's containers and volumes, and its registry entry.

    Nothing is deleted unless git would remove the worktree: uncommitted or untracked files
    block it, and the registry entry is kept if git still refuses so the stack can be found.

    Args:
        main: The main checkout.
        target: The worktree to remove.

    Raises:
        StackError: If target is the main checkout or not a worktree of this repository, it is
            locked, it holds uncommitted or untracked files, Docker cannot remove the stack, or
            git refuses.
    """
    target = target.resolve()
    main = main.resolve()
    if target == main:
        msg = "This is the main checkout. Name a worktree to remove."
        raise StackError(msg)
    worktrees = _worktrees(main)
    if target not in worktrees:
        msg = f"{target} is not a worktree of this repository"
        raise StackError(msg)
    # git refuses to remove a locked worktree, so check before the volumes are gone
    if any(line == "locked" or line.startswith("locked ") for line in worktrees[target]):
        msg = (
            f"{target} is locked. Unlock it with `git worktree unlock {target}`, "
            "then try again. Nothing was removed."
        )
        raise StackError(msg)

    key, project, ports = _find_stack(target)
    if key == MAIN_KEY or project == project_name(branch=None):
        msg = f"{target} resolves to the main stack, which teardown never removes"
        raise StackError(msg)

    if run_git(target, "status", "--porcelain"):
        msg = (
            f"{target} has uncommitted or untracked files, which block removal. "
            "Commit, stash, or delete them. Nothing was removed."
        )
        raise StackError(msg)

    if not _down_with_volumes(checkout=target, project=project, ports=ports):
        msg = (
            f"Could not remove the containers and volumes of {project}. "
            "Make sure Docker is running, then try again. Nothing else was removed."
        )
        raise StackError(msg)

    run_git(main, "worktree", "remove", str(target))
    console.print(f"removed worktree {target}")
    # A branch with a slash nests its worktree, and git leaves the emptied parents behind
    container = main / ".worktrees"
    for parent in target.parents:
        if parent == container or not parent.is_relative_to(container) or any(parent.iterdir()):
            break
        parent.rmdir()

    with Registry.locked() as registry:
        registry.remove(key)
    console.print(f"[green]✓[/green] removed stack {project}")


def prune(*, main: Path) -> list[str]:
    """Remove the stacks of worktrees whose directory no longer exists.

    Args:
        main: The main checkout; its own entry is never pruned.

    Returns:
        The registry keys that were pruned.
    """
    pruned: list[str] = []
    main_project = project_name(branch=None)
    for key, env in Registry.load().entries().items():
        if key == MAIN_KEY or env.project == main_project or env.checkout.exists():
            continue
        # The removed checkout cannot anchor Compose, but main's compose.yml defines the same stack
        if not _down_with_volumes(checkout=main, project=env.project, ports=env.ports):
            console.print(f"[yellow]kept {key}: could not remove {env.project}[/yellow]")
            continue
        with Registry.locked() as registry:
            registry.remove(key)
        console.print(f"pruned {key}")
        pruned.append(key)
    return pruned
