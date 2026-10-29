"""Find the PostgreSQL and Redis test servers this checkout's suite runs against.

`uv run duty test` starts the checkout's `postgres-test` and `redis-test` Compose services on its
slot's ports. A bare `uv run pytest` finds the same servers through the dev stack registry, so a
worktree never lands on another checkout's servers.
"""

import fcntl
import json
import os
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import asyncpg
import pytest
from scripts.devenv.compose import POSTGRES_PASSWORD, POSTGRES_USER, StackError
from scripts.devenv.ports import StackPorts
from scripts.devenv.registry import Registry, RegistryFormatError
from scripts.devenv.stack import TEST_SERVICES_HOST, checkout_identity

# Mirrors `--databases` on the redis-test service in compose.yml; database 0 is left unused
REDIS_DATABASES = 64
HOST_VAR = "VAPI_TEST_SERVICES_HOST"
POSTGRES_PORT_VAR = "VAPI_TEST_POSTGRES_PORT"
REDIS_PORT_VAR = "VAPI_TEST_REDIS_PORT"
NO_SLOT_MESSAGE = "this worktree has no stack slot yet; run `uv run duty test` once"
_RUN_LOCK = pytest.StashKey[TextIO]()


class ServiceLookupError(RuntimeError):
    """Raised when the suite cannot tell which test servers belong to this checkout."""


@dataclass(frozen=True)
class PostgresService:
    """Connection details for the PostgreSQL test server."""

    host: str
    port: int
    user: str
    password: str


@dataclass(frozen=True)
class RedisService:
    """Connection details for the Redis test server and this xdist worker's database on it."""

    host: str
    port: int
    db: int


@dataclass(frozen=True)
class ServiceAddresses:
    """Where this checkout's test servers listen."""

    host: str
    postgres_port: int
    redis_port: int


def _slot_ports(identify: Callable[[], tuple[Path, str | None]]) -> StackPorts:
    try:
        checkout, branch = identify()
    except (StackError, FileNotFoundError) as error:
        raise ServiceLookupError(str(error)) from error
    # Main always holds slot 0, so it needs no registry lookup
    if branch is None:
        return StackPorts.for_slot(0)
    try:
        slot = Registry.load().claimed_slot(branch)
    except (OSError, json.JSONDecodeError, KeyError, RegistryFormatError) as error:
        # Falling back to slot 0 would put a worktree on main's servers
        msg = f"could not read the dev stack registry to find {checkout}'s slot: {error}"
        raise ServiceLookupError(msg) from error
    if slot is None:
        raise ServiceLookupError(NO_SLOT_MESSAGE)
    return StackPorts.for_slot(slot)


def resolve_test_services(
    *, environ: Mapping[str, str], identify: Callable[[], tuple[Path, str | None]]
) -> ServiceAddresses:
    """Decide which test servers the suite uses.

    Variables set in the environment win, so CI and `duty test` choose explicitly. Otherwise the
    checkout's claimed slot decides: main uses slot 0 and a worktree uses its registry claim.

    Args:
        environ: The process environment.
        identify: Return the checkout root and its branch (`None` for main). Called only when
            the environment does not name both ports, so CI needs no git checkout.

    Returns:
        The host and ports of the checkout's test servers.

    Raises:
        ServiceLookupError: If only one port variable is set or a port is not a number, the
            checkout cannot be identified, a worktree has no slot claim, or the registry cannot
            be read.
    """
    host = environ.get(HOST_VAR) or TEST_SERVICES_HOST
    postgres_port = environ.get(POSTGRES_PORT_VAR)
    redis_port = environ.get(REDIS_PORT_VAR)
    if bool(postgres_port) != bool(redis_port):
        msg = f"{POSTGRES_PORT_VAR} and {REDIS_PORT_VAR} go together: set both or neither"
        raise ServiceLookupError(msg)
    if not postgres_port or not redis_port:
        ports = _slot_ports(identify)
        return ServiceAddresses(
            host=host, postgres_port=ports.postgres_test, redis_port=ports.redis_test
        )
    return ServiceAddresses(
        host=host,
        postgres_port=_parse_port(name=POSTGRES_PORT_VAR, value=postgres_port),
        redis_port=_parse_port(name=REDIS_PORT_VAR, value=redis_port),
    )


def _parse_port(*, name: str, value: str) -> int:
    try:
        return int(value)
    except ValueError as error:
        msg = f"{name} must be a port number, found {value!r}"
        raise ServiceLookupError(msg) from error


def redis_database(worker_id: str) -> int:
    """Return the Redis database an xdist worker owns, so parallel workers never share one.

    Args:
        worker_id: The xdist worker ID (`gw0`, `gw1`, ...) or `master` without xdist.

    Returns:
        gwN maps to N + 1. `master` runs alone, so it shares gw0's database.

    Raises:
        ServiceLookupError: If the worker needs a database past the server's last one.
    """
    db = 1 if worker_id == "master" else int(worker_id.removeprefix("gw")) + 1
    if db >= REDIS_DATABASES:
        msg = (
            f"xdist worker {worker_id} needs Redis database {db}, but redis-test has only "
            f"databases 1 to {REDIS_DATABASES - 1}. Run with `-n {REDIS_DATABASES - 1}` or fewer."
        )
        raise ServiceLookupError(msg)
    return db


async def admin_connection(postgres_service: PostgresService) -> asyncpg.Connection:
    """Connect to the test server's `postgres` maintenance database to create or drop databases.

    Uses asyncpg directly, since Tortoise cannot connect before the database exists.

    Args:
        postgres_service: The PostgreSQL test server.

    Returns:
        An open connection the caller must close.
    """
    try:
        return await asyncpg.connect(
            host=postgres_service.host,
            port=postgres_service.port,
            user=postgres_service.user,
            password=postgres_service.password,
            database="postgres",
        )
    except OSError:
        pytest.fail(
            f"test services are not running on {postgres_service.host}:{postgres_service.port}; "
            "run `uv run duty test` once (it starts them)"
        )


def run_lock_path(addresses: ServiceAddresses) -> Path:
    """Return the lock file shared by every run against one PostgreSQL test server.

    Args:
        addresses: The test servers a run uses.

    Returns:
        A path in the system temp directory, so runs from any checkout see the same lock.
    """
    return (
        Path(tempfile.gettempdir()) / f"vapi-pytest-{addresses.host}-{addresses.postgres_port}.lock"
    )


def acquire_run_lock(path: Path, *, on_wait: Callable[[], None]) -> TextIO:
    """Take the run lock, waiting for a run that already holds it.

    Two runs against one server would drop each other's per-worker databases and flush each
    other's Redis databases, so a second run waits for the first to finish.

    Args:
        path: The lock file.
        on_wait: Called once before blocking, so the caller can say why the run is paused.

    Returns:
        The open lock file. The lock is released when it is closed or the process exits.
    """
    handle = path.open("a")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        on_wait()
        fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def pytest_configure(config: pytest.Config) -> None:
    """Hold the run lock for the whole session in the controlling process."""
    if hasattr(config, "workerinput"):
        return
    here = Path(__file__).resolve().parent
    try:
        addresses = resolve_test_services(
            environ=os.environ, identify=lambda: checkout_identity(here)
        )
    except ServiceLookupError:
        # The service fixtures report this when a test needs the servers
        return
    path = run_lock_path(addresses)
    config.stash[_RUN_LOCK] = acquire_run_lock(
        path,
        on_wait=lambda: sys.stderr.write(
            f"Another test run is using the test servers on {addresses.host}:"
            f"{addresses.postgres_port}; waiting for it to finish\n"
        ),
    )


def pytest_unconfigure(config: pytest.Config) -> None:
    """Release the run lock."""
    handle = config.stash.get(_RUN_LOCK, None)
    if handle is not None:
        handle.close()


@pytest.fixture(scope="session")
def service_addresses() -> ServiceAddresses:
    """Resolve this checkout's test servers once per session, failing with the fix to apply."""
    here = Path(__file__).resolve().parent
    try:
        return resolve_test_services(environ=os.environ, identify=lambda: checkout_identity(here))
    except ServiceLookupError as error:
        pytest.fail(str(error))


@pytest.fixture(scope="session")
def postgres_service(service_addresses: ServiceAddresses) -> PostgresService:
    """Return the PostgreSQL test server's address and credentials."""
    return PostgresService(
        host=service_addresses.host,
        port=service_addresses.postgres_port,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
    )


@pytest.fixture(scope="session")
def redis_service(service_addresses: ServiceAddresses, worker_id: str) -> RedisService:
    """Return the Redis test server's address and the database this xdist worker owns."""
    try:
        db = redis_database(worker_id)
    except ServiceLookupError as error:
        pytest.fail(str(error))
    return RedisService(host=service_addresses.host, port=service_addresses.redis_port, db=db)
