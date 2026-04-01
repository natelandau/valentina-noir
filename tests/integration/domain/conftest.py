"""Domain integration test conftest — activate bridge fixtures for all domain tests."""

import pytest


@pytest.fixture(autouse=True)
def _autouse_clear_bridge_maps(_clear_bridge_maps: None) -> None:
    """Activate _clear_bridge_maps for every domain integration test."""


@pytest.fixture(autouse=True)
def _autouse_patch_pg_bridge(_patch_pg_bridge: None) -> None:
    """Activate _patch_pg_bridge for every domain integration test."""
