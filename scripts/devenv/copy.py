"""Copy main's database, bucket, and dev files into a worktree's stack."""

import re
import shutil
import subprocess
from pathlib import Path

from rich.console import Console

from scripts.devenv.compose import (
    POSTGRES_DB,
    POSTGRES_USER,
    StackError,
    compose_cmd,
    compose_env,
    is_fresh,
)
from scripts.devenv.ports import MAIN_PROJECT, StackPorts
from scripts.devenv.s3 import BUCKET, mirror_bucket

console = Console()
# The keys match the copied developers' hashes, and the generated secrets hold the HMAC key
# those hashes were computed with, so both must travel with the database
COPIED_FILES = ("api-keys.json", "generated.env")
S3_CONTAINER_PORT = "9000"
# The only stored column that holds an absolute storage URL
ASSET_TABLE = "s3_asset"
ASSET_URL_COLUMN = "public_url"
# `docker compose port` prints the published address, such as 127.0.0.1:24103
_ADDRESS = re.compile(r"^[0-9.]+:\d+$")


class MainNotInitializedError(StackError):
    """Raised when main's stack has no data to copy."""


def _s3_endpoint(*, checkout: Path, project: str) -> str:
    """Return the host URL of a running stack's storage, read from Docker's port mapping."""
    cmd = compose_cmd("port", "s3", S3_CONTAINER_PORT, checkout=checkout, project=project)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
    address = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    if result.returncode != 0 or not _ADDRESS.match(address):
        msg = f"Could not find the s3 port of {project}: {result.stderr.strip()}"
        raise StackError(msg)
    return f"http://{address}"


def _start_main_services(main: Path) -> None:
    """Start main's postgres and s3, never its api, so the copy cannot change main's data."""
    cmd = compose_cmd("up", "-d", "--wait", "postgres", "s3", checkout=main, project=MAIN_PROJECT)
    env = compose_env(ports=StackPorts.for_slot(0), debug=False)
    result = subprocess.run(cmd, env=env, check=False)  # noqa: S603
    if result.returncode != 0:
        msg = f"Could not start main's postgres and s3 (exit {result.returncode})"
        raise StackError(msg)


def _copy_database(*, main: Path, target: Path, target_project: str) -> None:
    dump_cmd = compose_cmd(
        "exec",
        "-T",
        "postgres",
        "pg_dump",
        "-Fc",
        "-U",
        POSTGRES_USER,
        POSTGRES_DB,
        checkout=main,
        project=MAIN_PROJECT,
    )
    restore_cmd = compose_cmd(
        "exec",
        "-T",
        "postgres",
        "pg_restore",
        "--clean",
        "--if-exists",
        "--no-owner",
        "-U",
        POSTGRES_USER,
        "-d",
        POSTGRES_DB,
        checkout=target,
        project=target_project,
    )
    dump = subprocess.Popen(dump_cmd, stdout=subprocess.PIPE)  # noqa: S603
    restore = subprocess.Popen(restore_cmd, stdin=dump.stdout)  # noqa: S603
    # Close the parent's copy so pg_dump sees a broken pipe if pg_restore exits early
    if dump.stdout is not None:
        dump.stdout.close()
    restore_code = restore.wait()
    dump_code = dump.wait()
    if dump_code != 0:
        msg = f"pg_dump from {MAIN_PROJECT} failed (exit {dump_code})"
        raise StackError(msg)
    if restore_code != 0:
        msg = f"pg_restore into {target_project} failed (exit {restore_code})"
        raise StackError(msg)


def _rewrite_asset_urls(
    *, target: Path, target_project: str, source: str, destination: str
) -> None:
    """Point copied asset rows at the target's storage instead of main's.

    Asset rows store the full public URL, which embeds the storage port of the stack that
    uploaded them.
    """
    # Both endpoints passed `_ADDRESS` validation, so they hold only digits, dots, and colons
    sql = (
        f"UPDATE {ASSET_TABLE} SET {ASSET_URL_COLUMN} = "  # noqa: S608
        f"replace({ASSET_URL_COLUMN}, '{source}/', '{destination}/')"
    )
    cmd = compose_cmd(
        "exec",
        "-T",
        "postgres",
        "psql",
        "-v",
        "ON_ERROR_STOP=1",
        "-U",
        POSTGRES_USER,
        "-d",
        POSTGRES_DB,
        "-c",
        sql,
        checkout=target,
        project=target_project,
    )
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)  # noqa: S603
    if result.returncode != 0:
        msg = f"Could not rewrite asset URLs in {target_project}: {result.stderr.strip()}"
        raise StackError(msg)


def _copy_dev_files(*, main: Path, target: Path) -> None:
    for name in COPIED_FILES:
        source = main / ".dev" / name
        if not source.exists():
            console.print(f"[yellow]Main has no .dev/{name}; skipped copying it[/yellow]")
            continue
        destination = target / ".dev" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o600)


def copy_from_main(*, main: Path, target: Path, target_project: str) -> None:
    """Fill a worktree's fresh stack with a copy of main's data.

    Start main's postgres and s3 when they are down. The target's postgres and s3 must be
    running and its bucket must exist.

    Args:
        main: The main checkout.
        target: The worktree checkout to fill.
        target_project: The worktree's Compose project name.

    Raises:
        MainNotInitializedError: If main's database was never initialized.
        StackError: If the dump or restore fails.
    """
    _start_main_services(main)
    if is_fresh(checkout=main, project=MAIN_PROJECT):
        msg = (
            f"Main's stack has no data to copy. Run `uv run duty up` in {main} first, "
            "then run `uv run duty up` here again."
        )
        raise MainNotInitializedError(msg)

    main_s3 = _s3_endpoint(checkout=main, project=MAIN_PROJECT)
    target_s3 = _s3_endpoint(checkout=target, project=target_project)
    console.print(f"Copying main's database into {target_project}...")
    _copy_database(main=main, target=target, target_project=target_project)
    _rewrite_asset_urls(
        target=target, target_project=target_project, source=main_s3, destination=target_s3
    )
    copied = mirror_bucket(source=main_s3, destination=target_s3, bucket=BUCKET)
    console.print(f"Copied {copied} objects from main's bucket")
    _copy_dev_files(main=main, target=target)
