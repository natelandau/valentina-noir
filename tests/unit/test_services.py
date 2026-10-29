"""Unit tests for finding this checkout's test servers."""

from pathlib import Path

import pytest
from scripts.devenv.registry import Registry

# These shadow the server fixtures, so the lookup can be tested while the servers are down
from tests.service_free import cleanup_pg_database, fx_redis, init_test_postgres  # noqa: F401
from tests.services import (
    NO_SLOT_MESSAGE,
    ServiceAddresses,
    ServiceLookupError,
    acquire_run_lock,
    redis_database,
    resolve_test_services,
    run_lock_path,
)


@pytest.fixture
def registry_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the dev stack registry at an empty file under tmp_path."""
    path = tmp_path / "registry.json"
    monkeypatch.setenv("VAPI_DEV_REGISTRY", str(path))
    return path


def _unreachable() -> tuple[Path, str | None]:
    msg = "the checkout must not be identified"
    raise AssertionError(msg)


def test_resolve_prefers_environment(registry_file: Path) -> None:
    """Verify exported variables win without identifying the checkout."""
    # Given
    environ = {
        "VAPI_TEST_SERVICES_HOST": "db.example",
        "VAPI_TEST_POSTGRES_PORT": "5555",
        "VAPI_TEST_REDIS_PORT": "6666",
    }

    # When
    addresses = resolve_test_services(environ=environ, identify=_unreachable)

    # Then
    assert addresses == ServiceAddresses(host="db.example", postgres_port=5555, redis_port=6666)
    assert not registry_file.exists()


def test_resolve_uses_worktree_claim(registry_file: Path, tmp_path: Path) -> None:
    """Verify a worktree without exported ports uses its registry slot."""
    # Given a worktree that holds slot 1 and another that holds slot 2
    with Registry.locked() as registry:
        registry.assign_slot(key="other", checkout=tmp_path / "other")
        registry.assign_slot(key="feat", checkout=tmp_path / "feat")

    # When
    addresses = resolve_test_services(environ={}, identify=lambda: (tmp_path / "feat", "feat"))

    # Then
    assert addresses == ServiceAddresses(host="127.0.0.1", postgres_port=24125, redis_port=24126)


def test_resolve_fails_for_unclaimed_worktree(registry_file: Path, tmp_path: Path) -> None:
    """Verify a worktree with no slot fails rather than using main's servers."""
    # Given an empty registry
    identify = lambda: (tmp_path / "feat", "feat")  # noqa: E731

    # When
    with pytest.raises(ServiceLookupError) as error:
        resolve_test_services(environ={}, identify=identify)

    # Then
    assert str(error.value) == NO_SLOT_MESSAGE


def test_resolve_fails_when_registry_is_unreadable(registry_file: Path, tmp_path: Path) -> None:
    """Verify an unreadable registry fails a worktree rather than falling back to slot 0."""
    # Given
    registry_file.write_text("{not json", encoding="utf-8")

    # When
    with pytest.raises(ServiceLookupError) as error:
        resolve_test_services(environ={}, identify=lambda: (tmp_path / "feat", "feat"))

    # Then
    assert "could not read the dev stack registry" in str(error.value)


def test_resolve_main_uses_slot_zero(registry_file: Path, tmp_path: Path) -> None:
    """Verify the main checkout uses slot 0 with no registry claim."""
    # Given an empty registry

    # When
    addresses = resolve_test_services(environ={}, identify=lambda: (tmp_path / "main", None))

    # Then
    assert addresses == ServiceAddresses(host="127.0.0.1", postgres_port=24105, redis_port=24106)


@pytest.mark.parametrize(
    ("worker", "expected"), [("master", 1), ("gw0", 1), ("gw1", 2), ("gw62", 63)]
)
def test_redis_database_maps_workers(worker: str, expected: int) -> None:
    """Verify each xdist worker gets its own Redis database from 1 to 63."""
    # Given a worker ID

    # When
    db = redis_database(worker)

    # Then
    assert db == expected


def test_redis_database_rejects_workers_past_the_last_database() -> None:
    """Verify a worker beyond database 63 fails with the worker count that fits."""
    # Given a worker that would need database 64

    # When
    with pytest.raises(ServiceLookupError) as error:
        redis_database("gw63")

    # Then
    assert "-n 63" in str(error.value)


@pytest.mark.parametrize(
    "environ", [{"VAPI_TEST_POSTGRES_PORT": "5555"}, {"VAPI_TEST_REDIS_PORT": "6666"}]
)
def test_resolve_rejects_one_port_variable(environ: dict[str, str]) -> None:
    """Verify naming only one test port fails rather than mixing in the slot's other port."""
    # Given one of the two port variables

    # When
    with pytest.raises(ServiceLookupError) as error:
        resolve_test_services(environ=environ, identify=_unreachable)

    # Then
    assert "set both or neither" in str(error.value)


def test_resolve_rejects_malformed_port() -> None:
    """Verify a port that is not a number fails with the variable that holds it."""
    # Given
    environ = {"VAPI_TEST_POSTGRES_PORT": "5555", "VAPI_TEST_REDIS_PORT": "redis"}

    # When
    with pytest.raises(ServiceLookupError) as error:
        resolve_test_services(environ=environ, identify=_unreachable)

    # Then
    assert "VAPI_TEST_REDIS_PORT" in str(error.value)
    assert "'redis'" in str(error.value)


def test_run_lock_path_is_shared_per_server() -> None:
    """Verify runs against one server share a lock file and other servers get their own."""
    # Given
    main = ServiceAddresses(host="127.0.0.1", postgres_port=24105, redis_port=24106)
    worktree = ServiceAddresses(host="127.0.0.1", postgres_port=24115, redis_port=24116)

    # When
    paths = (run_lock_path(main), run_lock_path(main), run_lock_path(worktree))

    # Then
    assert paths[0] == paths[1]
    assert paths[0] != paths[2]


def test_acquire_run_lock_takes_a_free_lock_without_waiting(tmp_path: Path) -> None:
    """Verify a run with no competitor never waits."""
    # Given
    waits: list[bool] = []

    # When
    handle = acquire_run_lock(tmp_path / "run.lock", on_wait=lambda: waits.append(True))
    handle.close()

    # Then
    assert waits == []


def test_acquire_run_lock_waits_for_a_held_lock(tmp_path: Path) -> None:
    """Verify a second run reports that it waits, then gets the lock once the first run ends."""
    # Given another run holds the lock, and ends when the second run starts waiting
    path = tmp_path / "run.lock"
    first = acquire_run_lock(path, on_wait=lambda: None)
    waits: list[bool] = []

    def first_run_ends() -> None:
        waits.append(True)
        first.close()

    # When
    second = acquire_run_lock(path, on_wait=first_run_ends)
    second.close()

    # Then
    assert waits == [True]
