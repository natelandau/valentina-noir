"""Unit tests for port blocks and project names."""

import re

import pytest
from scripts.devenv.ports import StackPorts, project_name


def test_for_slot_zero_is_main_block() -> None:
    """Verify slot 0 starts at the base port with fixed offsets."""
    # Given / When
    ports = StackPorts.for_slot(0)

    # Then
    assert ports.api == 24100
    assert ports.postgres == 24101
    assert ports.debugpy == 24107


def test_for_slot_offsets_by_ten() -> None:
    """Verify each slot shifts the block by ten ports."""
    # Given / When
    ports = StackPorts.for_slot(3)

    # Then
    assert ports.redis_test == 24136


def test_as_env_names_every_port() -> None:
    """Verify the environment mapping covers all eight ports."""
    # Given / When
    env = StackPorts.for_slot(1).as_env()

    # Then
    assert env["VAPI_DEV_API_PORT"] == "24110"
    assert env["VAPI_DEV_S3_CONSOLE_PORT"] == "24114"
    assert env["VAPI_DEV_DEBUGPY_PORT"] == "24117"
    assert len(env) == 8


def test_project_name_main() -> None:
    """Verify the main checkout has a fixed project name."""
    # Given / When / Then
    assert project_name(branch=None) == "vapi-main"


def test_project_name_slugs_branch() -> None:
    """Verify a branch becomes a slug plus digest that Compose accepts."""
    # Given / When
    name = project_name(branch="feature/Foo_Bar")

    # Then
    assert re.fullmatch(r"vapi-feature-foo-bar-[0-9a-f]{8}", name)
    assert re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name)
    assert len(name) <= 63


def test_project_name_truncates_long_branch() -> None:
    """Verify very long branch names still fit the Compose limit."""
    # Given
    branch = "feature/" + "x" * 200

    # When
    name = project_name(branch=branch)

    # Then
    assert len(name) <= 63
    assert re.fullmatch(r"[a-z0-9][a-z0-9_-]*", name)


@pytest.mark.parametrize(
    ("first", "second"), [("feature/foo", "feature-foo"), ("Feature", "feature")]
)
def test_project_name_keeps_similar_branches_apart(first: str, second: str) -> None:
    """Verify branches that slug identically still get distinct names."""
    # Given / When / Then
    assert project_name(branch=first) != project_name(branch=second)
