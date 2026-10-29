"""Unit tests for the dev stack registry."""

import json
import multiprocessing
import os
from pathlib import Path

import pytest
from scripts.devenv.ports import StackPorts, project_name
from scripts.devenv.registry import (
    Environment,
    Registry,
    RegistryFormatError,
    SlotConflictError,
    registry_path,
)


def make_env(key: str, slot: int, root: Path = Path("vapi-checkouts")) -> Environment:
    """Build an environment for a key and slot."""
    ports = StackPorts.for_slot(slot)
    return Environment(
        key=key,
        checkout=root / key,
        branch=key,
        slot=slot,
        project=project_name(branch=None if key == "main" else key),
        ports=ports,
        api_url=f"http://localhost:{ports.api}",
        api_url_from_containers=f"http://host.docker.internal:{ports.api}",
        healthz_url=f"http://localhost:{ports.api}/healthz",
        connection_sheet=root / key / ".dev" / "connection.md",
        keys_file=root / key / ".dev" / "api-keys.json",
        developers=[],
    )


def add_env(path: Path, key: str, slot: int) -> None:
    """Persist an environment through the locked registry."""
    with Registry.locked(path) as registry:
        registry.upsert(make_env(key, slot))


def add_many(path: Path, prefix: str) -> None:
    """Upsert 20 distinct environments, one lock at a time."""
    for index in range(20):
        add_env(path, f"{prefix}-{index}", index + 1)


def test_registry_path_honors_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Verify the environment variable overrides the default location."""
    # Given
    monkeypatch.setenv("VAPI_DEV_REGISTRY", str(tmp_path / "r.json"))

    # When / Then
    assert registry_path() == tmp_path / "r.json"


def test_assign_slot_main_is_zero(tmp_path: Path) -> None:
    """Verify the main checkout always gets slot 0."""
    # Given
    registry = Registry.load(tmp_path / "r.json")

    # When
    slot = registry.assign_slot(key="main", checkout=tmp_path)

    # Then
    assert slot == 0


def test_assign_slot_takes_lowest_free(tmp_path: Path) -> None:
    """Verify a gap in the slots is reused."""
    # Given
    registry = Registry.load(tmp_path / "r.json")
    registry.upsert(make_env("a", 1))
    registry.upsert(make_env("c", 3))

    # When
    slot = registry.assign_slot(key="b", checkout=tmp_path)

    # Then
    assert slot == 2


def test_assign_slot_is_stable_for_same_key(tmp_path: Path) -> None:
    """Verify a registered key keeps its slot."""
    # Given
    registry = Registry.load(tmp_path / "r.json")
    registry.upsert(make_env("a", 1))
    registry.upsert(make_env("b", 2))

    # When
    slot = registry.assign_slot(key="b", checkout=tmp_path)

    # Then
    assert slot == 2


def test_remove_frees_slot(tmp_path: Path) -> None:
    """Verify removing an environment makes its slot available."""
    # Given
    registry = Registry.load(tmp_path / "r.json")
    registry.upsert(make_env("a", 1))

    # When
    registry.remove("a")

    # Then
    assert registry.assign_slot(key="z", checkout=tmp_path) == 1
    assert registry.entries() == {}


def test_file_has_schema_version_and_description(tmp_path: Path) -> None:
    """Verify the saved file carries its header fields and round-trips."""
    # Given
    path = tmp_path / "state" / "r.json"
    add_env(path, "main", 0)

    # When
    raw = json.loads(path.read_text())
    loaded = Registry.load(path).entries()["main"]

    # Then
    assert raw["schema_version"] == 1
    assert raw["description"]
    assert raw["environments"]["main"]["ports"]["api"] == 24100
    assert loaded == make_env("main", 0)


def test_concurrent_writers_do_not_lose_entries(tmp_path: Path) -> None:
    """Verify the file lock serializes writers from separate processes."""
    # Given
    path = tmp_path / "r.json"
    procs = [multiprocessing.Process(target=add_many, args=(path, prefix)) for prefix in ("p", "q")]

    # When
    for proc in procs:
        proc.start()
    for proc in procs:
        proc.join()

    # Then
    assert all(proc.exitcode == 0 for proc in procs)
    assert len(Registry.load(path).entries()) == 40


def test_assign_slot_reserves_before_upsert(tmp_path: Path) -> None:
    """Verify two keys assigned back to back never share a slot."""
    # Given
    registry = Registry.load(tmp_path / "r.json")

    # When
    first = registry.assign_slot(key="a", checkout=tmp_path / "a")
    second = registry.assign_slot(key="b", checkout=tmp_path / "b")

    # Then
    assert first != second


def test_claims_persist_without_upsert(tmp_path: Path) -> None:
    """Verify a reserved slot survives a save and reload."""
    # Given
    path = tmp_path / "r.json"
    with Registry.locked(path) as registry:
        registry.assign_slot(key="a", checkout=tmp_path / "a")

    # When
    with Registry.locked(path) as registry:
        other = registry.assign_slot(key="b", checkout=tmp_path / "b")

    # Then
    assert json.loads(path.read_text())["slots"]["a"]["slot"] == 1
    assert other == 2


def test_assign_slot_rejects_key_held_by_existing_checkout(tmp_path: Path) -> None:
    """Verify a second live checkout cannot take over a registered key."""
    # Given
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    registry = Registry.load(tmp_path / "r.json")
    registry.assign_slot(key="a", checkout=first)

    # When / Then
    with pytest.raises(SlotConflictError, match="first"):
        registry.assign_slot(key="a", checkout=second)


def test_assign_slot_reassigns_key_from_missing_checkout(tmp_path: Path) -> None:
    """Verify a key whose checkout is gone moves to the new checkout, keeping its slot."""
    # Given
    gone, new = tmp_path / "gone", tmp_path / "new"
    new.mkdir()
    registry = Registry.load(tmp_path / "r.json")
    slot = registry.assign_slot(key="a", checkout=gone)

    # When
    reassigned = registry.assign_slot(key="a", checkout=new)

    # Then
    assert reassigned == slot


def test_remove_frees_claim(tmp_path: Path) -> None:
    """Verify removing a key also releases its reserved slot."""
    # Given
    registry = Registry.load(tmp_path / "r.json")
    registry.assign_slot(key="a", checkout=tmp_path)

    # When
    registry.remove("a")

    # Then
    assert registry.assign_slot(key="b", checkout=tmp_path) == 1


@pytest.mark.parametrize(
    "content", ['{"environments": {}}', '{"schema_version": 2, "environments": {}}']
)
def test_load_rejects_unsupported_schema(tmp_path: Path, content: str) -> None:
    """Verify a missing or unknown schema version fails with a clear error."""
    # Given
    path = tmp_path / "r.json"
    path.write_text(content)

    # When / Then
    with pytest.raises(RegistryFormatError, match="schema_version"):
        Registry.load(path)


def test_save_writes_owner_only_file(tmp_path: Path) -> None:
    """Verify the registry file, which holds raw API keys, is readable by its owner only."""
    # Given
    path = tmp_path / "environments.json"

    # When
    with Registry.locked(path) as registry:
        registry.upsert(make_env("main", 0))

    # Then
    assert path.stat().st_mode & 0o777 == 0o600


def test_save_tightens_a_stale_temp_file(tmp_path: Path) -> None:
    """Verify a leftover temp file with a looser mode does not leak into the registry file."""
    # Given a temp file from an interrupted save, readable by everyone
    path = tmp_path / "environments.json"
    stale = tmp_path / f".environments.json.{os.getpid()}.tmp"
    stale.write_text("{}")
    stale.chmod(0o644)

    # When
    with Registry.locked(path) as registry:
        registry.upsert(make_env("main", 0))

    # Then
    assert path.stat().st_mode & 0o777 == 0o600


def test_entry_records_keys_file(tmp_path: Path) -> None:
    """Verify each entry stores and reloads the path of its checkout's API key file."""
    # Given an entry saved to the registry
    path = tmp_path / "r.json"
    add_env(path, "feat", 1)

    # When
    raw = json.loads(path.read_text())["environments"]["feat"]
    loaded = Registry.load(path).entries()["feat"]

    # Then
    assert raw["keys_file"] == str(Path("vapi-checkouts") / "feat" / ".dev" / "api-keys.json")
    assert loaded.keys_file == Path("vapi-checkouts") / "feat" / ".dev" / "api-keys.json"


@pytest.mark.parametrize(
    "content",
    ["{not json", '{"schema_version": 1}', '{"schema_version": 1, "environments": {"a": {}}}'],
)
def test_load_reports_unreadable_file_with_its_path(tmp_path: Path, content: str) -> None:
    """Verify a corrupt or incomplete registry raises one error naming the file."""
    # Given
    path = tmp_path / "r.json"
    path.write_text(content)

    # When / Then
    with pytest.raises(RegistryFormatError, match=str(path)):
        Registry.load(path)


def test_save_syncs_bytes_to_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify the registry is flushed to disk before it replaces the old file."""
    # Given
    synced: list[int] = []
    real_fsync = os.fsync
    monkeypatch.setattr(os, "fsync", lambda fd: synced.append(fd) or real_fsync(fd))

    # When
    Registry.load(tmp_path / "r.json").save()

    # Then
    assert synced
