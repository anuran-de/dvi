"""Business-level blast radius: which external consumers a data incident reaches,
and how that lifts severity.

An incident's data-asset blast radius is projected onto the dbt *exposures*
downstream of it. The worst consumer criticality can *raise* incident severity
(never lower it), and only for a *material* change — an immaterial flicker under
a critical dashboard stays low. Rendering groups the affected consumers by type
for the operator.
"""

from __future__ import annotations

from dataclasses import dataclass

from dvi.lineage import Criticality, Exposure, LineageGraph

# Single source of truth for the materiality floor; incidents.incident imports this.
MAGNITUDE_MATERIAL = 0.1

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
_CRIT_TO_SEVERITY = {
    Criticality.LOW: "low",
    Criticality.MEDIUM: "medium",
    Criticality.HIGH: "high",
    Criticality.CRITICAL: "critical",
}
# Fixed display order + human labels for the grouped block.
_TYPE_ORDER = ["application", "ml", "dashboard", "notebook", "analysis"]
_TYPE_LABEL = {
    "application": "Applications",
    "ml": "ML features",
    "dashboard": "Dashboards",
    "notebook": "Notebooks",
    "analysis": "Analyses",
}


@dataclass(frozen=True)
class BusinessImpact:
    exposures: tuple[Exposure, ...]
    by_type: dict[str, list[Exposure]]
    max_criticality: Criticality | None


def assess_impact(affected_assets: set[str], lineage: LineageGraph) -> BusinessImpact:
    """Exposures reachable from the incident's data-asset blast radius."""
    exposures = tuple(lineage.exposures_downstream_of(affected_assets))
    by_type: dict[str, list[Exposure]] = {}
    for exposure in exposures:
        by_type.setdefault(exposure.type, []).append(exposure)
    worst = max((e.criticality for e in exposures), default=None)
    return BusinessImpact(exposures=exposures, by_type=by_type, max_criticality=worst)


def criticality_to_severity(criticality: Criticality) -> str:
    return _CRIT_TO_SEVERITY[criticality]


def escalate_severity(base: str, impact: BusinessImpact, max_magnitude: float) -> str:
    """Raise ``base`` to the consumer-implied severity — only if material."""
    if max_magnitude < MAGNITUDE_MATERIAL or impact.max_criticality is None:
        return base
    implied = criticality_to_severity(impact.max_criticality)
    return max(base, implied, key=_SEVERITY_ORDER.__getitem__)


def render_business_impact(impact: BusinessImpact) -> list[str]:
    """Grouped, deterministically-ordered terminal lines (empty if no impact)."""
    if not impact.exposures:
        return []
    lines = ["  Business impact:"]
    for type_ in _TYPE_ORDER:
        group = impact.by_type.get(type_)
        if not group:
            continue
        rendered = ", ".join(
            f"{e.name} [{e.criticality.name}]" + (f" @{e.owner}" if e.owner else "")
            for e in group
        )
        lines.append(f"    {_TYPE_LABEL[type_]} ({len(group)}): {rendered}")
    return lines
