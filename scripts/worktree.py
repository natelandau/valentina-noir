"""Dev-only: give each git worktree its own PostgreSQL database, Redis database, and API port.

Branches in separate worktrees change data and migrations at the same time, so one shared
database lets a branch's migration or test data break another's. Each worktree instead works
on a copy of the main checkout's database, its own Redis logical database (caches, sessions,
rate limits, and the SAQ queue), and its own API port, all recorded in its `.env.secret`.
Every worktree shares the main checkout's PostgreSQL and Redis containers.

Run as a module from the checkout it acts on:

    uv run python -m scripts.worktree create BRANCH    # from the main checkout
    uv run python -m scripts.worktree provision        # from inside a worktree
    uv run python -m scripts.worktree prune
    uv run python -m scripts.worktree teardown [PATH]
"""

import hashlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import click
from dotenv import dotenv_values
from rich.console import Console

from scripts.dev_data.safety import LOCAL_HOSTS

console = Console()

ENV_FILE = ".env.secret"
# Local files a worktree needs that git does not carry: they are ignored in every checkout
COPIED_FILES = (ENV_FILE, "CLAUDE.local.md")
DATABASE_PREFIX = "vapi_wt_"
# A restore lands here first and is renamed when it finishes, so an interrupted copy is never
# mistaken for a finished database
RESTORING_SUFFIX = "_restoring"
_DIGEST_LENGTH = 8
# Postgres truncates identifiers at 63 bytes; leave room for the digest and the restoring suffix
_MAX_SLUG = 63 - len(DATABASE_PREFIX) - 1 - _DIGEST_LENGTH - len(RESTORING_SUFFIX)
# Redis's default `databases` setting, which compose-db.yml does not change
REDIS_DATABASES = 16

# Must match the defaults in vapi.config.base, which cannot be imported without building Settings
DEFAULT_POSTGRES_HOST = "localhost"
DEFAULT_DATABASE = "valentina-noir"
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_PORT = 8000

# Credentials compose-db.yml gives the containers
CONTAINER_POSTGRES_USER = "valentina"
CONTAINER_REDIS_PASSWORD = "redispassword"  # noqa: S105

KEY_POSTGRES_HOST = "VAPI_POSTGRES__HOST"
KEY_DATABASE = "VAPI_POSTGRES__DATABASE"
KEY_REDIS_URL = "VAPI_REDIS__URL"
KEY_PORT = "VAPI_SERVER__PORT"


@dataclass(frozen=True)
class Checkouts:
    """The main checkout and every linked worktree, as git records them."""

    main: Path
    worktrees: list[Path]

    @classmethod
    def discover(cls, cwd: Path) -> "Checkouts":
        """Read the checkouts of the repository that holds cwd from `git worktree list`.

        Args:
            cwd (Path): Any directory inside the repository.

        Returns:
            Checkouts: The main checkout and every linked worktree.
        """
        listing = _git(cwd, "worktree", "list", "--porcelain")
        paths = [
            Path(line.removeprefix("worktree "))
            for line in listing.splitlines()
            if line.startswith("worktree ")
        ]
        return cls(main=paths[0], worktrees=paths[1:])

    @property
    def live_worktrees(self) -> list[Path]:
        """Worktrees whose directory still exists; git lists deleted ones until pruned."""
        return [path for path in self.worktrees if path.exists()]


@dataclass(frozen=True)
class MainSettings:
    """The main checkout's connection settings that every worktree derives its own from."""

    postgres_host: str
    database: str
    redis_url: str
    port: int

    @classmethod
    def load(cls, main: Path) -> "MainSettings":
        """Read the main checkout's `.env.secret`, falling back to the application defaults.

        Args:
            main (Path): The main checkout.

        Returns:
            MainSettings: The main checkout's settings.
        """
        env = read_env(main / ENV_FILE)
        return cls(
            postgres_host=env.get(KEY_POSTGRES_HOST, DEFAULT_POSTGRES_HOST),
            database=env.get(KEY_DATABASE, DEFAULT_DATABASE),
            redis_url=env.get(KEY_REDIS_URL, DEFAULT_REDIS_URL),
            port=int(env.get(KEY_PORT, DEFAULT_PORT)),
        )

    @property
    def redis_db(self) -> int:
        """The Redis logical database the main checkout uses."""
        return redis_db(self.redis_url)


def _git(cwd: Path, *args: str) -> str:
    """Run git in cwd and return its output, exiting with git's message when it fails."""
    result = subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        sys.exit(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def toplevel(cwd: Path) -> Path:
    """Return the root of the checkout that holds cwd."""
    return Path(_git(cwd, "rev-parse", "--show-toplevel").strip())


def slug(key: str) -> str:
    """Turn a worktree's path into a readable fragment Postgres accepts unquoted.

    Args:
        key (str): The worktree's path below `.worktrees/`, or its absolute path when outside it.

    Returns:
        str: Lowercase letters and digits joined by underscores, cut to fit an identifier.
    """
    joined = "_".join(re.findall(r"[a-z0-9]+", key.lower()))
    return joined[:_MAX_SLUG].rstrip("_") or "worktree"


def database_for(worktree: Path, main: Path) -> str:
    """Name the PostgreSQL database a worktree owns from where it sits.

    The slug keeps the name readable, and a digest of the exact path keeps it unique: branch
    names that differ only in punctuation, case, or a long shared head slug alike.

    Args:
        worktree (Path): The worktree.
        main (Path): The main checkout.

    Returns:
        str: The database name.
    """
    try:
        key = worktree.relative_to(main / ".worktrees").as_posix()
    except ValueError:
        key = worktree.as_posix()
    digest = hashlib.sha256(key.encode()).hexdigest()[:_DIGEST_LENGTH]
    return f"{DATABASE_PREFIX}{slug(key)}_{digest}"


def stale_databases(present: list[str], keep: set[str]) -> list[str]:
    """Pick the worktree databases whose worktree is gone, never a database this module did not make."""
    return sorted(name for name in present if name.startswith(DATABASE_PREFIX) and name not in keep)


def read_env(env_file: Path) -> dict[str, str]:
    """Read an env file without building Settings, which may refuse a half-configured file."""
    if not env_file.exists():
        return {}
    # A blank value means unset, matching how the app falls back to its default
    return {key: value for key, value in dotenv_values(env_file).items() if value}


def rewrite_env(env_file: Path, values: dict[str, str]) -> None:
    """Set each key in an env file in place, keeping every other line and comment.

    Args:
        env_file (Path): The env file to edit.
        values (dict[str, str]): Keys to set, appended when the file lacks them.
    """
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    seen: set[str] = set()
    for index, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        # Rewrite every occurrence: dotenv keeps the last one, so a stale duplicate would win
        if key in values:
            lines[index] = f"{key}={values[key]}"
            seen.add(key)
    lines.extend(f"{key}={value}" for key, value in values.items() if key not in seen)
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def redis_db(url: str) -> int:
    """Return the logical database a Redis URL selects, which is 0 when the URL names none."""
    path = urlsplit(url).path.strip("/")
    return int(path) if path else 0


def with_redis_db(url: str, database: int) -> str:
    """Return the same Redis URL pointed at another logical database."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database}", parts.query, parts.fragment))


def slot_of(env: dict[str, str], main: MainSettings) -> int | None:
    """Return the slot a worktree's env already claims, or None when it still mirrors main's.

    A worktree's slot is its Redis logical database; its API port is main's port plus the slot.
    """
    if KEY_REDIS_URL not in env:
        return None
    database = redis_db(env[KEY_REDIS_URL])
    return None if database in {0, main.redis_db} else database


def choose_slot(current: int | None, taken: set[int], main: MainSettings) -> int:
    """Keep a worktree's slot when no other worktree holds it, else take the lowest free one.

    Args:
        current (int | None): The slot the worktree's env already claims.
        taken (set[int]): Slots other live worktrees hold.
        main (MainSettings): The main checkout's settings, whose Redis database is never a slot.

    Returns:
        int: The worktree's slot.
    """
    if current is not None and current not in taken:
        return current
    free = [n for n in range(1, REDIS_DATABASES) if n not in taken and n != main.redis_db]
    if not free:
        sys.exit(
            f"every Redis database is in use by a worktree; tear one down first ({sorted(taken)})"
        )
    return free[0]


def _quoted(database: str) -> str:
    # The one guard between these commands and a database someone fills by hand
    if not database.startswith(DATABASE_PREFIX) or not re.fullmatch(r"[a-z0-9_]+", database):
        sys.exit(
            f"refusing to act on '{database}': only {DATABASE_PREFIX}* databases are managed here"
        )
    return f'"{database}"'


class LocalServices:
    """The main checkout's PostgreSQL and Redis containers, reached with `docker compose exec`."""

    def __init__(self, main: Path) -> None:
        # The containers bind-mount their data relative to the compose file, so a worktree's
        # copy would recreate them over empty data. Compose interpolates ${VAR} from .env only,
        # so pass the env file to pick up settings such as VAPI_POSTGRES__PORT.
        env_file = main / ENV_FILE
        env_args = ["--env-file", str(env_file)] if env_file.exists() else []
        self.compose = ["docker", "compose", *env_args, "-f", str(main / "compose-db.yml")]

    def up(self) -> None:
        """Start both containers if they are not already running, quietly unless it fails."""
        result = subprocess.run(  # noqa: S603
            [*self.compose, "up", "-d", "--wait"], capture_output=True, text=True, check=False
        )
        if result.returncode:
            sys.exit(f"starting the database containers failed: {result.stderr.strip()}")

    def _exec(self, service: str, *args: str) -> str:
        result = subprocess.run(  # noqa: S603
            [*self.compose, "exec", "-T", service, *args],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            sys.exit(f"{service} {args[0]} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def _psql(self, sql: str) -> str:
        return self._exec(
            "postgres", "psql", "-U", CONTAINER_POSTGRES_USER, "-d", "postgres", "-tAc", sql
        )

    def databases(self) -> list[str]:
        """List every database on the server."""
        return self._psql("select datname from pg_database").splitlines()

    def create_database(self, database: str) -> None:
        """Create an empty worktree database."""
        self._psql(f"create database {_quoted(database)}")

    def drop_database(self, database: str) -> None:
        """Drop a worktree database, ending any session still on it."""
        self._psql(f"drop database if exists {_quoted(database)} with (force)")

    def rename_database(self, source: str, target: str) -> None:
        """Rename a worktree database, which nothing may be connected to."""
        self._psql(f"alter database {_quoted(source)} rename to {_quoted(target)}")

    def clone_database(self, source: str, target: str) -> None:
        """Copy one database into another inside the PostgreSQL container.

        pg_dump reads a consistent snapshot while other sessions stay connected, which
        `create database ... template` refuses, so the main checkout's server may keep running.

        Args:
            source (str): The database to copy.
            target (str): The empty worktree database to restore into.
        """
        exec_postgres = [*self.compose, "exec", "-T", "postgres"]
        with subprocess.Popen(  # noqa: S603
            [*exec_postgres, "pg_dump", "-U", CONTAINER_POSTGRES_USER, "--format=custom", source],
            stdout=subprocess.PIPE,
        ) as dump:
            restore = subprocess.run(  # noqa: S603
                [
                    *exec_postgres,
                    "pg_restore",
                    "-U",
                    CONTAINER_POSTGRES_USER,
                    "--no-owner",
                    "--no-privileges",
                    "--exit-on-error",
                    "-d",
                    target,
                ],
                stdin=dump.stdout,
                check=False,
            )
            if dump.stdout:
                dump.stdout.close()
        if dump.returncode or restore.returncode:
            self.drop_database(target)
            sys.exit(
                f"copying {source} into {target} failed: "
                f"pg_dump exited {dump.returncode}, pg_restore {restore.returncode}"
            )

    def _redis(self, database: int, *args: str) -> str:
        return self._exec(
            "redis",
            "redis-cli",
            "-a",
            CONTAINER_REDIS_PASSWORD,
            "--no-auth-warning",
            "-n",
            str(database),
            *args,
        )

    def redis_databases_with_keys(self) -> set[int]:
        """List the Redis logical databases that hold at least one key, in one round trip."""
        keyspace = self._redis(0, "INFO", "keyspace")
        return {int(match) for match in re.findall(r"^db(\d+):keys=[1-9]", keyspace, re.MULTILINE)}

    def flush_redis(self, database: int) -> None:
        """Delete every key in a Redis logical database."""
        self._redis(database, "FLUSHDB")


def copy_local_files(main: Path, worktree: Path) -> None:
    """Copy the main checkout's env and local instruction files into a worktree, replacing any there.

    Args:
        main (Path): The main checkout.
        worktree (Path): The worktree to copy into.
    """
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
        if ignored.returncode:
            console.print(f"[yellow]skipped {name}: this branch does not ignore it[/yellow]")
            continue
        shutil.copyfile(source, worktree / name)
        console.print(f"copied {name}")


def provision(cwd: Path) -> None:
    """Give the worktree that holds cwd its own database, Redis database, and port.

    The database starts as a copy of the main checkout's. Running it again keeps the
    database and slot already there and only re-points `.env.secret` at them.

    Args:
        cwd (Path): Any directory inside the worktree.
    """
    checkouts = Checkouts.discover(cwd)
    here = toplevel(cwd)
    if here == checkouts.main:
        sys.exit("this is the main checkout, which keeps its own database; run this in a worktree")
    env_file = here / ENV_FILE
    if not env_file.exists():
        sys.exit(f"{env_file} is missing; create the worktree with `duty worktree`")

    main = MainSettings.load(checkouts.main)
    if main.postgres_host not in LOCAL_HOSTS:
        sys.exit(
            f"postgres host '{main.postgres_host}' is not local; worktree databases are local only"
        )

    taken = {
        slot
        for path in checkouts.live_worktrees
        if path != here and (slot := slot_of(read_env(path / ENV_FILE), main)) is not None
    }
    current = slot_of(read_env(env_file), main)
    slot = choose_slot(current, taken, main)
    database = database_for(here, checkouts.main)

    services = LocalServices(checkouts.main)
    services.up()
    present = services.databases()
    if database in present:
        console.print(f"{database} is already there")
    elif main.database in present:
        staging = database + RESTORING_SUFFIX
        # Left behind when an earlier copy was interrupted
        services.drop_database(staging)
        services.create_database(staging)
        services.clone_database(main.database, staging)
        services.rename_database(staging, database)
        console.print(f"created {database} as a copy of {main.database}")
    else:
        services.create_database(database)
        console.print(f"created {database} empty, since {main.database} is not there")
    if slot != current:
        # A slot freed by a removed worktree may still hold its keys
        services.flush_redis(slot)

    port = main.port + slot
    rewrite_env(
        env_file,
        {
            KEY_DATABASE: database,
            KEY_REDIS_URL: with_redis_db(main.redis_url, slot),
            KEY_PORT: str(port),
        },
    )
    console.print(
        f"[green]✓[/green] {ENV_FILE} uses database {database}, Redis database {slot}, port {port}"
    )


def prune(cwd: Path) -> None:
    """Drop the databases and flush the Redis databases of worktrees that no longer exist.

    Args:
        cwd (Path): Any directory inside the repository.
    """
    checkouts = Checkouts.discover(cwd)
    main = MainSettings.load(checkouts.main)
    live = checkouts.live_worktrees
    services = LocalServices(checkouts.main)
    services.up()

    keep = {database_for(path, checkouts.main) for path in live}
    for database in stale_databases(services.databases(), keep):
        services.drop_database(database)
        console.print(f"dropped {database}")

    used = {0, main.redis_db} | {
        slot for path in live if (slot := slot_of(read_env(path / ENV_FILE), main)) is not None
    }
    for slot in sorted(services.redis_databases_with_keys() - used):
        services.flush_redis(slot)
        console.print(f"flushed Redis database {slot}")


def create(cwd: Path, branch: str) -> Path:
    """Create `.worktrees/<branch>` on a new branch and copy in the main checkout's local files.

    Args:
        cwd (Path): Any directory inside the repository.
        branch (str): The new branch, which also names the worktree directory.

    Returns:
        Path: The new worktree.
    """
    main = Checkouts.discover(cwd).main
    path = main / ".worktrees" / branch
    _git(main, "worktree", "add", str(path), "-b", branch)
    console.print(f"created worktree {path} on branch {branch}")
    copy_local_files(main, path)
    return path


def teardown(cwd: Path, target: Path | None) -> None:
    """Remove a worktree, then drop its database and flush its Redis database.

    git refuses to remove a worktree with uncommitted changes, and nothing is dropped then.

    Args:
        cwd (Path): Any directory inside the repository.
        target (Path | None): The worktree to remove, or the one that holds cwd.
    """
    checkouts = Checkouts.discover(cwd)
    worktree = target.resolve() if target else toplevel(cwd)
    if worktree == checkouts.main:
        sys.exit("this is the main checkout; name a worktree to tear down")
    if worktree not in checkouts.worktrees:
        sys.exit(f"{worktree} is not a worktree of this repository")

    main = MainSettings.load(checkouts.main)
    slot = slot_of(read_env(worktree / ENV_FILE), main)
    database = database_for(worktree, checkouts.main)

    _git(checkouts.main, "worktree", "remove", str(worktree))
    console.print(f"removed worktree {worktree}")
    # A branch with a slash nests its worktree, and git leaves the emptied parents behind
    container = checkouts.main / ".worktrees"
    for parent in worktree.parents:
        if parent == container or not parent.is_relative_to(container) or any(parent.iterdir()):
            break
        parent.rmdir()
    services = LocalServices(checkouts.main)
    services.up()
    services.drop_database(database)
    console.print(f"dropped {database}")
    others = {
        other
        for path in checkouts.live_worktrees
        if path != worktree and (other := slot_of(read_env(path / ENV_FILE), main)) is not None
    }
    # Another worktree may still claim this slot until its next provision moves it
    if slot is not None and slot not in others:
        services.flush_redis(slot)
        console.print(f"flushed Redis database {slot}")


@click.group()
def cli() -> None:
    """Manage per-worktree databases for local development."""


@cli.command(name="create")
@click.argument("branch")
def create_command(branch: str) -> None:
    """Create .worktrees/BRANCH on a new branch with the main checkout's local files."""
    create(Path.cwd(), branch)


@cli.command(name="provision")
@click.argument("path", required=False, type=click.Path(exists=True, path_type=Path))
def provision_command(path: Path | None) -> None:
    """Give a worktree (default: this one) its own database, Redis database, and port."""
    provision(path or Path.cwd())


@cli.command(name="prune")
def prune_command() -> None:
    """Remove the databases of worktrees that no longer exist."""
    prune(Path.cwd())


@cli.command(name="teardown")
@click.argument("path", required=False, type=click.Path(path_type=Path))
def teardown_command(path: Path | None) -> None:
    """Remove a worktree (default: this one) and its databases."""
    teardown(Path.cwd(), path)


if __name__ == "__main__":
    cli()
