"""Statistics DTOs."""

from __future__ import annotations

from beanie import PydanticObjectId  # noqa: TC002
from pydantic import BaseModel, Field, computed_field


class RollStatistics(BaseModel):
    """Roll statistics."""

    botches: int
    successes: int
    failures: int
    criticals: int
    total_rolls: int
    average_difficulty: float | None = None
    average_pool: float | None = None
    top_traits: list[dict[str, int | str | PydanticObjectId]] = Field(default_factory=list)

    @computed_field
    def criticals_percentage(self) -> float:
        """Calculate and return the percentage of critical successes.

        Returns:
            float: The percentage of critical successes. Returns 0 if no rolls have been made.
        """
        return self.criticals / self.total_rolls * 100 if self.total_rolls > 0 else 0

    @computed_field
    def success_percentage(self) -> float:
        """Calculate and return the percentage of successful rolls.

        Returns:
            float: The percentage of successful rolls. Returns 0 if no rolls have been made.
        """
        return self.successes / self.total_rolls * 100 if self.total_rolls > 0 else 0

    @computed_field
    def failure_percentage(self) -> float:
        """Calculate and return the percentage of failed rolls.

        Returns:
            float: The percentage of failed rolls. Returns 0 if no rolls have been made.
        """
        return self.failures / self.total_rolls * 100 if self.total_rolls > 0 else 0

    @computed_field
    def botch_percentage(self) -> float:
        """Calculate and return the percentage of botched rolls.

        Returns:
            float: The percentage of botched rolls. Returns 0 if no rolls have been made.
        """
        return self.botches / self.total_rolls * 100 if self.total_rolls > 0 else 0
