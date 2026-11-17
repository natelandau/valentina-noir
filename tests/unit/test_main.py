"""Unit tests for the application entrypoint."""

from __future__ import annotations

import os
import sys

import pytest

import vapi.__main__ as entrypoint
from vapi.config import settings


@pytest.mark.parametrize(
    ("vapi_debug", "litestar_debug", "expected"),
    [(False, "1", "0"), (True, "0", "1"), (False, None, "0")],
    ids=["ignores-litestar-on", "ignores-litestar-off", "unset"],
)
def test_run_cli_sets_litestar_debug_from_settings(
    monkeypatch: pytest.MonkeyPatch, vapi_debug: bool, litestar_debug: str | None, expected: str
) -> None:
    """Verify VAPI_DEBUG alone decides debug mode, whatever LITESTAR_DEBUG holds."""
    # Given LITESTAR_DEBUG disagrees with settings.debug
    monkeypatch.setattr(settings, "debug", vapi_debug)
    if litestar_debug is None:
        monkeypatch.delenv("LITESTAR_DEBUG", raising=False)
    else:
        monkeypatch.setenv("LITESTAR_DEBUG", litestar_debug)
    monkeypatch.setattr(entrypoint, "litestar_group", lambda: 0)
    # run_cli mutates process-wide state; register it so monkeypatch restores it afterwards
    monkeypatch.setattr(sys, "path", list(sys.path))
    for key in ("LITESTAR_APP", "LITESTAR_APP_NAME", "LITESTAR_HOST", "LITESTAR_PORT"):
        monkeypatch.delenv(key, raising=False)

    # When the CLI entrypoint runs
    with pytest.raises(SystemExit):
        entrypoint.run_cli()

    # Then LITESTAR_DEBUG matches settings.debug
    assert os.environ["LITESTAR_DEBUG"] == expected
