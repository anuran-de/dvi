"""Root-cause ranking via deterministic graph + temporal reasoning.

A change event is a candidate cause for an observed symptom only when it is
*corroborated*: it happened **before** the symptom, within a plausible lead
window, and it targeted an asset that is the symptomatic asset itself or lies
**upstream** of it in the lineage graph. Isolated symptoms with no such change
produce no candidate — that is the symptom/incident boundary.

Scoring is a transparent weighted blend of coverage (how many symptoms the
change accounts for) and temporal proximity. These hand-set weights are the
deterministic baseline; a *calibrated* confidence learned from held-out
incidents replaces the blend in milestone M3.
"""

from __future__ import annotations

from datetime import timedelta

from dvi.lineage import LineageGraph

from .models import ChangeEvent, Observation, RootCauseCandidate

DEFAULT_MAX_LEAD = timedelta(hours=24)

COVERAGE_WEIGHT = 0.6
PROXIMITY_WEIGHT = 0.4


def _targets_relevant_to(change: ChangeEvent, asset: str, lineage: LineageGraph) -> bool:
    for target in change.targets:
        if target == asset or lineage.is_downstream_of(asset, target):
            return True
    return False


def _explains(
    change: ChangeEvent, obs: Observation, lineage: LineageGraph, max_lead: timedelta
) -> bool:
    if change.timestamp > obs.observed_at:
        return False
    if obs.observed_at - change.timestamp > max_lead:
        return False
    return _targets_relevant_to(change, obs.asset, lineage)


def rank_root_causes(
    observations: list[Observation],
    changes: list[ChangeEvent],
    lineage: LineageGraph,
    *,
    max_lead: timedelta = DEFAULT_MAX_LEAD,
) -> list[RootCauseCandidate]:
    """Rank change events by how well they explain the observed symptoms."""
    if not observations:
        return []

    candidates: list[RootCauseCandidate] = []
    for change in changes:
        explained = [o for o in observations if _explains(change, o, lineage, max_lead)]
        if not explained:
            continue

        coverage = len(explained) / len(observations)
        proximity = sum(
            1.0 - (o.observed_at - change.timestamp) / max_lead for o in explained
        ) / len(explained)
        score = COVERAGE_WEIGHT * coverage + PROXIMITY_WEIGHT * proximity

        candidates.append(
            RootCauseCandidate(
                change=change,
                score=score,
                explained=explained,
                evidence=_build_evidence(change, explained, lineage),
            )
        )

    candidates.sort(key=lambda c: (c.score, c.change.timestamp), reverse=True)
    return candidates


def _build_evidence(
    change: ChangeEvent, explained: list[Observation], lineage: LineageGraph
) -> list[str]:
    label = change.label or change.id
    evidence: list[str] = []

    lead = min(o.observed_at - change.timestamp for o in explained)
    minutes = int(lead.total_seconds() // 60)
    evidence.append(f"Change '{label}' was deployed {minutes} min before the first symptom.")

    for obs in explained:
        sym = obs.symptom
        direct = any(t == obs.asset for t in change.targets)
        relation = "directly changed" if direct else "is upstream of"
        detail = sym.description or f"{sym.signature} on {sym.column}"
        evidence.append(f"'{label}' {relation} {obs.asset}, where DVI observed: {detail}")

    upstream_of_all = {
        t
        for t in change.targets
        if all(t == o.asset or lineage.is_downstream_of(o.asset, t) for o in explained)
    }
    if upstream_of_all:
        evidence.append(
            "No corresponding change was observed upstream of the targeted asset(s)."
        )
    return evidence
