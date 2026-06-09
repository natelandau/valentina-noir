"""Production-safety guard for the destructive dev-data population script."""

from typing import Protocol

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class _PostgresLike(Protocol):
    host: str


class _SettingsLike(Protocol):
    postgres: _PostgresLike


def production_warning(settings: _SettingsLike) -> str | None:
    """Return a human-readable reason when the target looks like production, else None.

    Production is inferred from a non-local Postgres host: the destructive reset must only
    run against a local development database. `debug` is intentionally not used as a signal
    because it defaults to False, which would block legitimate local runs.
    """
    if settings.postgres.host not in LOCAL_HOSTS:
        return f"postgres host '{settings.postgres.host}' is not local"
    return None
