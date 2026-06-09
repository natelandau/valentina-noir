"""Unit tests for the dev-data production-safety guard."""

from types import SimpleNamespace

from scripts.dev_data.safety import production_warning


def _settings(*, host: str) -> SimpleNamespace:
    """Build a minimal settings stub exposing the postgres host the guard inspects."""
    return SimpleNamespace(postgres=SimpleNamespace(host=host))


def test_local_host_is_not_production() -> None:
    """Any local Postgres host is treated as a safe development target."""
    # Given / When / Then: no local host is flagged
    assert production_warning(_settings(host="localhost")) is None
    assert production_warning(_settings(host="127.0.0.1")) is None
    assert production_warning(_settings(host="::1")) is None


def test_non_local_host_is_flagged() -> None:
    """A non-local Postgres host is flagged as production-like."""
    # Given: a remote host
    settings = _settings(host="db.prod.example.com")

    # When: evaluating the guard
    reason = production_warning(settings)

    # Then: it is flagged, naming the host
    assert reason is not None
    assert "db.prod.example.com" in reason
