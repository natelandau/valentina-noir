"""RNG character generation schemas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vapi.db.models import Trait


@dataclass
class DotsPerExperienceLevel:
    """Dot increase per AutoGenExperienceLevel."""

    INTERMEDIATE: int
    ADVANCED: int
    ELITE: int
    NEW: int = 0


@dataclass
class TraitWithValue:
    """Trait with a value."""

    trait: Trait
    value: int
