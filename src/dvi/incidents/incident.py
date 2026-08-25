"""Incident synthesis.

Turns the top-ranked root-cause candidate into an operator-facing incident:
a summary, a severity, the affected downstream assets, and the evidence bundle.

Crucially, ``synthesize_incident`` returns ``None`` when nothing is corroborated
— symptoms without a cause never become incidents. No confidence *percentage*
is emitted here: DVI presents rank + evidence until the calibrated model (M3)
can produce a *measured* confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from dvi.lineage import LineageGraph
from dvi.rca import Observation, RootCauseCandidate

MAGNITUDE_MATERIAL = 0.1


@dataclass
class Incident:
    title: str
    severity: str
    summary: str
    primary_cause: RootCauseCandidate
    affected_assets: set[str] = field(default_factory=set)
    evidence: list[str] = field(default_factory=list)
    detected_at: datetime | None = None
    change_at: datetime | None = None


def _severity(max_magnitude: float, propagates: bool) -> str:
    if max_magnitude < MAGNITUDE_MATERIAL:
        return "low"
    return "high" if propagates else "medium"


def synthesize_incident(
    ranked: list[RootCauseCandidate],
    lineage: LineageGraph,
    observations: list[Observation],
) -> Incident | None:
    """Build an incident from the top candidate, or ``None`` if uncorroborated."""
    if not ranked:
        return None

    top = ranked[0]

    downstream: set[str] = set()
    for target in top.change.targets:
        downstream |= lineage.downstream(target)
    # Purely downstream impact: exclude the changed asset(s) themselves.
    affected = (downstream | {o.asset for o in top.explained}) - set(top.change.targets)

    propagates = bool(affected)
    max_magnitude = max((o.symptom.magnitude for o in top.explained), default=0.0)
    severity = _severity(max_magnitude, propagates)

    worst = max(top.explained, key=lambda o: o.symptom.magnitude)
    label = top.change.label or top.change.id
    summary = (
        f"Suspected data incident from change '{label}'. "
        f"{worst.symptom.description or worst.symptom.signature} "
        f"on {worst.asset}; {len(affected)} downstream asset(s) affected."
    )

    detected_at = max(o.observed_at for o in top.explained)
    return Incident(
        title=f"Semantic change in {worst.symptom.column} - {label}",
        severity=severity,
        summary=summary,
        primary_cause=top,
        affected_assets=affected,
        evidence=list(top.evidence),
        detected_at=detected_at,
        change_at=top.change.timestamp,
    )
