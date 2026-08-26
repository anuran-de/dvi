"""A Symptom is the output of a change-signature detector.

A symptom is *not* an incident. It records that a deterministic signature fired
on a column, with a magnitude and the observable evidence behind it. Whether a
symptom becomes an incident is decided later by corroboration (time × deployment
× downstream propagation).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Symptom(BaseModel):
    """A fired change signature on a single column."""

    signature: str
    column: str
    magnitude: float = Field(ge=0.0, le=1.0)
    description: str = ""
    evidence: dict[str, object] = Field(default_factory=dict)

    # Populated by substitution-style signatures.
    from_value: str | None = None
    to_value: str | None = None

    # Measured probability that this symptom is a real change (set by the M3
    # calibration layer when a model is supplied; ``None`` leaves M1/M2 behavior).
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
