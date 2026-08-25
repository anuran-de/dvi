"""The ColumnProfile — a point-in-time statistical summary of one column.

This is the unit that makes semantic change detection possible: it carries the
*value distribution* (top-K frequencies), not just structural stats.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ColumnProfile(BaseModel):
    """A statistical summary of a single column at a point in time."""

    name: str
    row_count: int
    null_count: int
    distinct_count: int
    top_k: dict[str, int] = Field(default_factory=dict)

    @property
    def non_null_count(self) -> int:
        return self.row_count - self.null_count

    @property
    def null_rate(self) -> float:
        if self.row_count == 0:
            return 0.0
        return self.null_count / self.row_count

    def value_share(self, value: str) -> float:
        """Fraction of non-null rows equal to ``value`` (0.0 if unseen)."""
        if self.non_null_count == 0:
            return 0.0
        return self.top_k.get(value, 0) / self.non_null_count
