"""Incident synthesis.

Turns the top-ranked root-cause candidate into an operator-facing incident:
a summary, a severity, the affected downstream assets, and the evidence bundle.

Crucially, ``synthesize_incident`` returns ``None`` when nothing is corroborated
— symptoms without a cause never become incidents. When the primary symptom
carries a calibrated ``confidence`` (M3), the incident surfaces it as a
*measured* probability; otherwise ``confidence`` stays ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from dvi.lineage import LineageGraph
from dvi.rca import Observation, RootCauseCandidate

from .impact import MAGNITUDE_MATERIAL, BusinessImpact, assess_impact, escalate_severity


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
    # Measured confidence of the primary symptom, when a calibration model ran.
    confidence: float | None = None
    business_impact: BusinessImpact | None = None


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

    # Data-only blast radius: exposure nodes must never leak into affected_assets.
    downstream_data = lineage.data_downstream_of(set(top.change.targets))
    # Purely downstream impact: exclude the changed asset(s) themselves.
    affected = (downstream_data | {o.asset for o in top.explained}) - set(top.change.targets)

    propagates = bool(affected)
    max_magnitude = max((o.symptom.magnitude for o in top.explained), default=0.0)
    severity = _severity(max_magnitude, propagates)

    # Assess business impact over the blast radius plus the changed targets
    # themselves, so an exposure hanging directly off a changed model is caught.
    impact_scope = affected | set(top.change.targets)
    impact = assess_impact(impact_scope, lineage)
    severity = escalate_severity(severity, impact, max_magnitude)

    worst = max(top.explained, key=lambda o: o.symptom.magnitude)
    label = top.change.label or top.change.id
    summary = (
        f"Suspected data incident from change '{label}'. "
        f"{worst.symptom.description or worst.symptom.signature} "
        f"on {worst.asset}; {len(affected)} downstream asset(s) affected."
    )
    if impact.exposures:
        counts = ", ".join(
            f"{len(group)} {type_}" for type_, group in impact.by_type.items()
        )
        summary += (
            f" Reaches {len(impact.exposures)} external consumer(s): {counts} "
            f"(worst: {impact.max_criticality.name})."
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
        confidence=worst.symptom.confidence,
        business_impact=impact if impact.exposures else None,
    )
