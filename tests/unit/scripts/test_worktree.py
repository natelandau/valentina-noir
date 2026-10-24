"""Unit tests for the per-worktree database helpers."""

import re
from pathlib import Path

import pytest
from scripts.worktree import (
    DATABASE_PREFIX,
    KEY_DATABASE,
    KEY_PORT,
    KEY_REDIS_URL,
    RESTORING_SUFFIX,
    MainSettings,
    choose_slot,
    database_for,
    read_env,
    redis_db,
    rewrite_env,
    slot_of,
    slug,
    stale_databases,
    with_redis_db,
)

MAIN = MainSettings(
    postgres_host="localhost",
    database="valentina-noir",
    redis_url="redis://:pw@localhost:6379/0",
    port=8001,
)


def test_slug_joins_lowercase_words() -> None:
    """Verify branch names become lowercase words joined by underscores."""
    # Given a branch name with a slash, dashes, and capitals
    key = "feat/Add-Login"

    # When slugged
    result = slug(key)

    # Then only lowercase letters, digits, and underscores remain
    assert result == "feat_add_login"


def test_slug_cuts_long_keys_to_fit_an_identifier() -> None:
    """Verify a long key is cut so the full database name fits a Postgres identifier."""
    # Given a key far longer than an identifier allows
    key = "a" * 80

    # When naming a worktree at that path
    result = database_for(Path("/repo/.worktrees") / key, Path("/repo"))

    # Then the name, even with the restoring suffix, fits in 63 bytes
    assert len(result + RESTORING_SUFFIX) <= 63
    assert result.startswith(DATABASE_PREFIX + "aaaa")


def test_database_for_names_worktrees_under_dot_worktrees() -> None:
    """Verify a worktree under .worktrees/ is named from its path below that folder."""
    # Given a worktree inside the main checkout's .worktrees folder
    main = Path("/repo")
    worktree = main / ".worktrees" / "feat" / "login"

    # When naming its database
    result = database_for(worktree, main)

    # Then the name is the prefix, the slugged relative path, and a digest
    assert re.fullmatch(r"vapi_wt_feat_login_[0-9a-f]{8}", result)


def test_database_for_names_worktrees_outside_dot_worktrees() -> None:
    """Verify a worktree elsewhere is named from its absolute path."""
    # Given a worktree outside the main checkout
    main = Path("/repo")
    worktree = Path("/elsewhere/other")

    # When naming its database
    result = database_for(worktree, main)

    # Then the name comes from the absolute path
    assert re.fullmatch(r"vapi_wt_elsewhere_other_[0-9a-f]{8}", result)


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("feat/add-login", "feat-add-login"),
        ("Feature", "feature"),
        ("a" * 80 + "-one", "a" * 80 + "-two"),
    ],
)
def test_database_for_keeps_similar_branches_apart(first: str, second: str) -> None:
    """Verify branches whose slugs match still get different databases."""
    # Given two worktrees whose names slug alike
    main = Path("/repo")

    # When naming both databases
    first_name = database_for(main / ".worktrees" / first, main)
    second_name = database_for(main / ".worktrees" / second, main)

    # Then the names differ
    assert first_name != second_name


def test_stale_databases_only_picks_prefixed_names_without_a_worktree() -> None:
    """Verify pruning never touches databases this module did not create."""
    # Given the main database, a live worktree's database, and an orphaned one
    present = ["valentina-noir", "postgres", "vapi_wt_live", "vapi_wt_gone"]

    # When picking stale databases
    result = stale_databases(present, keep={"vapi_wt_live"})

    # Then only the orphan is chosen
    assert result == ["vapi_wt_gone"]


def test_rewrite_env_replaces_and_appends_keys(tmp_path: Path) -> None:
    """Verify existing keys change in place, comments survive, and missing keys are appended."""
    # Given an env file with a comment, a key to change, and an unrelated key
    env_file = tmp_path / ".env.secret"
    env_file.write_text(
        "# comment\nVAPI_NAME=test\nVAPI_POSTGRES__DATABASE=valentina-noir\n", encoding="utf-8"
    )

    # When rewriting one existing and one missing key
    rewrite_env(env_file, {KEY_DATABASE: "vapi_wt_x", KEY_PORT: "8002"})

    # Then the file keeps its other lines and holds both values
    assert env_file.read_text(encoding="utf-8").splitlines() == [
        "# comment",
        "VAPI_NAME=test",
        "VAPI_POSTGRES__DATABASE=vapi_wt_x",
        "VAPI_SERVER__PORT=8002",
    ]
    assert read_env(env_file)[KEY_PORT] == "8002"


def test_rewrite_env_replaces_every_duplicate_key(tmp_path: Path) -> None:
    """Verify a key set twice is rewritten everywhere so the last occurrence cannot win."""
    # Given an env file that sets the database twice
    env_file = tmp_path / ".env.secret"
    env_file.write_text(
        "VAPI_POSTGRES__DATABASE=one\nVAPI_POSTGRES__DATABASE=two\n", encoding="utf-8"
    )

    # When rewriting the database
    rewrite_env(env_file, {KEY_DATABASE: "vapi_wt_x"})

    # Then the file resolves to the new value
    assert read_env(env_file)[KEY_DATABASE] == "vapi_wt_x"


def test_read_env_treats_blank_values_as_unset(tmp_path: Path) -> None:
    """Verify a blank value falls back like a missing key instead of reaching int()."""
    # Given an env file with a blank port
    env_file = tmp_path / ".env.secret"
    env_file.write_text("VAPI_SERVER__PORT=\n", encoding="utf-8")

    # When reading it
    env = read_env(env_file)

    # Then the blank key is absent
    assert KEY_PORT not in env


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("redis://localhost:6379", 0),
        ("redis://localhost:6379/", 0),
        ("redis://:pw@localhost:6379/3", 3),
    ],
)
def test_redis_db_reads_the_logical_database(url: str, expected: int) -> None:
    """Verify the logical database comes from the URL path and defaults to 0."""
    # Given / When / Then
    assert redis_db(url) == expected


def test_with_redis_db_keeps_credentials() -> None:
    """Verify switching the logical database keeps the host and password."""
    # Given / When
    result = with_redis_db("redis://:pw@localhost:6379/0", 4)

    # Then
    assert result == "redis://:pw@localhost:6379/4"


def test_slot_of_ignores_an_env_that_mirrors_main() -> None:
    """Verify a freshly copied env file has no slot yet."""
    # Given / When / Then
    assert slot_of({KEY_REDIS_URL: MAIN.redis_url}, MAIN) is None
    assert slot_of({}, MAIN) is None


def test_slot_of_reads_an_assigned_slot() -> None:
    """Verify a provisioned env file claims its Redis database as its slot."""
    # Given / When / Then
    assert slot_of({KEY_REDIS_URL: "redis://:pw@localhost:6379/5"}, MAIN) == 5


def test_choose_slot_keeps_a_free_current_slot() -> None:
    """Verify re-provisioning keeps the slot a worktree already holds."""
    # Given / When / Then
    assert choose_slot(current=4, taken={1, 2}, main=MAIN) == 4


def test_choose_slot_takes_the_lowest_free_slot() -> None:
    """Verify a new or conflicting worktree gets the lowest slot nobody holds."""
    # Given / When / Then
    assert choose_slot(current=None, taken={1, 2}, main=MAIN) == 3
    assert choose_slot(current=2, taken={1, 2}, main=MAIN) == 3


def test_choose_slot_exits_when_every_slot_is_taken() -> None:
    """Verify running out of Redis databases exits instead of sharing one."""
    # Given every slot except main's database is taken
    taken = set(range(1, 16))

    # When / Then
    with pytest.raises(SystemExit):
        choose_slot(current=None, taken=taken, main=MAIN)
