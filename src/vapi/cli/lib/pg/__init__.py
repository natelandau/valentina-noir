"""PostgreSQL bootstrap syncers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self


@dataclass
class SyncCounts:
    """Track create/update counts during fixture sync."""

    created: int = 0
    updated: int = 0
    total: int = 0

    def __iadd__(self, other: SyncCounts) -> Self:
        """Accumulate counts from another SyncCounts."""
        self.created += other.created
        self.updated += other.updated
        self.total += other.total
        return self
