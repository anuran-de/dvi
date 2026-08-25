"""End-to-end orchestration: two snapshots of an asset in, an incident out.

This wires the M1 walking skeleton together:

    profile(before/after) -> detectors -> observations
                                              |
                       changes + lineage -> rank_root_causes
                                              |
                                     synthesize_incident
"""

from __future__ import annotations

from datetime import datetime

import polars as pl

from dvi.detection import (
    detect_case_format_normalization,
    detect_numeric_distribution_shift,
    detect_unit_scale_shift,
    detect_value_substitution,
)
from dvi.incidents import Incident, synthesize_incident
from dvi.lineage import LineageGraph
from dvi.profiling import profile_column
from dvi.rca import ChangeEvent, Observation, rank_root_causes

# Registry of the active signatures. Each takes (baseline, current) profiles and
# returns a Symptom or None.
_DETECTORS = [
    detect_value_substitution,
    detect_case_format_normalization,
    detect_unit_scale_shift,
    detect_numeric_distribution_shift,
]

# Precedence: a more specific signature suppresses a more general one when both
# fire on the same column, so reporting both would be noise.
#   #5 (unit/scale) is a special case of #4 (distribution shift) -> keep #5.
#   #2 (re-spelling) is a special case of #1 (substitution)      -> keep #2.
_SUPPRESSES = {
    "unit_scale_shift": {"numeric_distribution_shift"},
    "case_format_normalization": {"value_substitution"},
}


def _apply_precedence(symptoms: list):
    """Drop symptoms that a more specific co-located signature has superseded."""
    suppressed: set[tuple[str, str]] = set()
    for s in symptoms:
        for victim in _SUPPRESSES.get(s.signature, ()):
            suppressed.add((s.column, victim))
    return [s for s in symptoms if (s.column, s.signature) not in suppressed]


def detect_symptoms(
    before: pl.DataFrame, after: pl.DataFrame, columns: list[str] | None = None
):
    """Profile the given columns before/after and run every active detector."""
    if columns is None:
        columns = [c for c in before.columns if c in after.columns]

    symptoms = []
    for column in columns:
        baseline = profile_column(before[column].rename(column))
        current = profile_column(after[column].rename(column))
        for detector in _DETECTORS:
            symptom = detector(baseline, current)
            if symptom is not None:
                symptoms.append(symptom)
    return _apply_precedence(symptoms)


def analyze_change(
    *,
    asset: str,
    before: pl.DataFrame,
    after: pl.DataFrame,
    observed_at: datetime,
    lineage: LineageGraph,
    changes: list[ChangeEvent],
    columns: list[str] | None = None,
) -> Incident | None:
    """Analyze a before/after snapshot of one asset and return an incident.

    Returns ``None`` when either no signature fires or nothing corroborates the
    symptoms into an incident.
    """
    symptoms = detect_symptoms(before, after, columns)
    if not symptoms:
        return None

    observations = [Observation(asset, observed_at, s) for s in symptoms]
    ranked = rank_root_causes(observations, changes, lineage)
    return synthesize_incident(ranked, lineage, observations)
