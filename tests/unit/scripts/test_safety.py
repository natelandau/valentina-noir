"""Unit tests for the dev-data production-safety guard."""

from types import SimpleNamespace

from scripts.dev_data.safety import production_warning


def _settings(*, debug: bool, host: str) -> SimpleNamespace:
    """Build a minimal settings stub with the fields the guard inspects."""
    return SimpleNamespace(debug=debug, postgres=SimpleNamespace(host=host))


def test_local_debug_target_is_not_production() -> None:
    """Local debug target should not be flagged as production."""
    # Given: debug on, local host
    settings = _settings(debug=True, host="localhost")

    # When / Then: no warning
    assert production_warning(settings) is None


def test_non_local_host_is_flagged() -> None:
    """Non-local Postgres host should be flagged as production-like."""
    # Given: debug on but a remote host
    settings = _settings(debug=True, host="db.prod.example.com")

    # When: evaluating the guard
    reason = production_warning(settings)

    # Then: it is flagged as production-like
    assert reason is not None
    assert "db.prod.example.com" in reason


def test_debug_off_is_flagged() -> None:
    """Debug off should be flagged as production-like."""
    # Given: a local host but debug off
    settings = _settings(debug=False, host="127.0.0.1")

    # When: evaluating the guard
    reason = production_warning(settings)

    # Then: it is flagged
    assert reason is not None
    assert "debug" in reason.lower()
