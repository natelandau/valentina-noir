"""Statistics DTOs."""

from uuid import UUID

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
    top_traits: list[dict[str, int | str | UUID]] = Field(default_factory=list)

    @computed_field
    def criticals_percentage(self) -> float:
        """Calculate the percentage of critical successes."""
        return self.criticals / self.total_rolls * 100 if self.total_rolls > 0 else 0

    @computed_field
    def success_percentage(self) -> float:
        """Calculate the percentage of successful rolls."""
        return self.successes / self.total_rolls * 100 if self.total_rolls > 0 else 0

    @computed_field
    def failure_percentage(self) -> float:
        """Calculate the percentage of failed rolls."""
        return self.failures / self.total_rolls * 100 if self.total_rolls > 0 else 0

    @computed_field
    def botch_percentage(self) -> float:
        """Calculate the percentage of botched rolls."""
        return self.botches / self.total_rolls * 100 if self.total_rolls > 0 else 0
