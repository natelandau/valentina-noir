"""Port blocks and Compose project names for isolated dev stacks."""

import hashlib
import re
from dataclasses import dataclass, fields
from typing import Self

PORT_BASE = 24100
SLOT_WIDTH = 10

MAIN_PROJECT = "vapi-main"
# Compose limits project names to 63 characters
_MAX_PROJECT_LENGTH = 63
_DIGEST_LENGTH = 8


@dataclass(frozen=True)
class StackPorts:
    """Host ports published by one stack, all bound to 127.0.0.1."""

    api: int
    postgres: int
    redis: int
    s3: int
    s3_console: int
    postgres_test: int
    redis_test: int
    debugpy: int

    @classmethod
    def for_slot(cls, slot: int) -> Self:
        """Build the port block for a slot.

        Args:
            slot: Zero-based slot number. Slot 0 is the main checkout.

        Returns:
            The ports at consecutive offsets from `PORT_BASE + SLOT_WIDTH * slot`.
        """
        base = PORT_BASE + SLOT_WIDTH * slot
        return cls(**{field.name: base + index for index, field in enumerate(fields(cls))})

    def as_env(self) -> dict[str, str]:
        """Return the ports as `VAPI_DEV_<NAME>_PORT` environment variables."""
        return {
            f"VAPI_DEV_{field.name.upper()}_PORT": str(getattr(self, field.name))
            for field in fields(self)
        }


def project_name(*, branch: str | None) -> str:
    """Return the Compose project name for a checkout.

    Args:
        branch: The worktree's branch, or `None` for the main checkout.

    Returns:
        `vapi-main` for main, otherwise `vapi-<slug>-<digest>`. The digest comes from the raw
        branch name so names like `feature/foo` and `feature-foo` stay distinct.
    """
    if branch is None:
        return MAIN_PROJECT

    digest = hashlib.sha256(branch.encode()).hexdigest()[:_DIGEST_LENGTH]
    slug = re.sub(r"[^a-z0-9]+", "-", branch.lower()).strip("-")
    room = _MAX_PROJECT_LENGTH - len(f"vapi--{digest}")
    slug = slug[:room].strip("-")
    return f"vapi-{slug}-{digest}" if slug else f"vapi-{digest}"
