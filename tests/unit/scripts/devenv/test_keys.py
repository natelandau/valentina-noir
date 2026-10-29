"""Unit tests for the raw API key store."""

import json
import stat
from pathlib import Path
from uuid import uuid4

import pytest
from scripts.dev_data.api_keys import DevApiKey
from scripts.devenv import keys as keys_module
from scripts.devenv.keys import load_keys, record_keys


def _key(api_key: str) -> DevApiKey:
    return DevApiKey(
        api_key=api_key,
        developer_id=uuid4(),
        username=f"dev-{api_key}",
        email=f"{api_key}@example.com",
        is_global_admin=False,
    )


@pytest.fixture(autouse=True)
def keys_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the key store at a temporary file."""
    path = tmp_path / ".dev" / "api-keys.json"
    monkeypatch.setattr(keys_module, "KEYS_FILE", path)
    return path


def test_load_keys_missing_file_is_empty() -> None:
    """A checkout that never minted a key has no keys."""
    # Given / When / Then
    assert load_keys() == {}


def test_record_keys_replace_overwrites() -> None:
    """replace=True drops every previously recorded key."""
    # Given: one recorded key
    old, new = _key("old"), _key("new")
    record_keys([old], replace=True)

    # When: replacing with a different set
    record_keys([new], replace=True)

    # Then: only the new key remains
    assert load_keys() == {new.developer_id: "new"}


def test_record_keys_merge_keeps_others() -> None:
    """replace=False keeps keys of other developers and updates the same developer."""
    # Given: two recorded keys
    first, second = _key("first"), _key("second")
    record_keys([first, second], replace=True)

    # When: merging a rotated key for the first developer and a new third key
    rotated = DevApiKey(
        api_key="rotated",
        developer_id=first.developer_id,
        username=first.username,
        email=first.email,
        is_global_admin=False,
    )
    third = _key("third")
    record_keys([rotated, third], replace=False)

    # Then: everything is present with the latest value per developer
    assert load_keys() == {
        first.developer_id: "rotated",
        second.developer_id: "second",
        third.developer_id: "third",
    }


def test_record_keys_file_is_private(keys_file: Path) -> None:
    """The key file holds raw secrets, so only the owner can read it."""
    # Given / When
    record_keys([_key("secret")], replace=True)

    # Then
    assert stat.S_IMODE(keys_file.stat().st_mode) == 0o600
    assert "secret" in json.loads(keys_file.read_text()).values()


def test_load_keys_corrupt_file_names_the_file(keys_file: Path) -> None:
    """A corrupt key file fails with an error that names it."""
    # Given
    keys_file.parent.mkdir(parents=True)
    keys_file.write_text("{not json")

    # When / Then
    with pytest.raises(ValueError, match=r"api-keys\.json"):
        load_keys()
