"""Production-safety guard for the destructive dev-data population script."""

from typing import Protocol

LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


class _PostgresLike(Protocol):
    host: str


class _SettingsLike(Protocol):
    debug: bool
    postgres: _PostgresLike


def production_warning(settings: _SettingsLike) -> str | None:
    """Return a human-readable reason when the target looks like production, else None.

    There is no environment enum on Settings, so production is inferred from two signals:
    `debug` being off, or a non-local Postgres host. Either trips the guard.
    """
    if not settings.debug:
        return "settings.debug is False, which looks like a production configuration"
    if settings.postgres.host not in LOCAL_HOSTS:
        return f"postgres host '{settings.postgres.host}' is not local"
    return None
