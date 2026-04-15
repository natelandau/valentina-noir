"""System health schemas."""

from dataclasses import dataclass
from typing import Literal

from vapi import __version__ as current_version

__all__ = ("SystemHealth",)


@dataclass
class SystemHealth:
    """System health."""

    database_status: Literal["online", "offline"]
    cache_status: Literal["online", "offline"]
    database_latency_ms: float | None
    cache_latency_ms: float | None
    uptime: str
    version: str = current_version
