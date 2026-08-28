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

# Import from the calibration *submodules*, not the package, to avoid a cycle:
# the package __init__ pulls loader -> dataset -> benchmark -> back into this
# module, so importing the package here would see it half-initialized.
from dvi.calibration.model import LogisticModel
from dvi.calibration.score import attach_confidence
from dvi.detection import (
    DEFAULT_DISTRIBUTION_THRESHOLD,
    detect_case_format_normalization,
    detect_category_split_merge,
    detect_numeric_distribution_shift,
    detect_unit_scale_shift,
    detect_value_substitution,
)
from dvi.incidents import Incident, synthesize_incident
from dvi.lineage import LineageGraph
from dvi.profiling import ColumnProfile, profile_column
from dvi.rca import ChangeEvent, Observation, rank_root_causes

# Precedence: a more specific signature suppresses a more general one when both
# fire on the same column, so reporting both would be noise.
#   #5 (unit/scale) is a special case of #4 (distribution shift) -> keep #5.
#   #2 (re-spelling) is a special case of #1 (substitution)      -> keep #2.
_SUPPRESSES = {
    "unit_scale_shift": {"numeric_distribution_shift"},
    "case_format_normalization": {"value_substitution"},
}


def _build_detectors(dist_threshold: float):
    """The active signature registry. Each takes (baseline, current) profiles.

    The numeric distribution-shift threshold is the one continuously tunable knob
    (used by the benchmark to trace the recall/false-positive operating curve);
    the categorical signatures are fixed.
    """
    return [
        detect_value_substitution,
        detect_case_format_normalization,
        detect_category_split_merge,
        detect_unit_scale_shift,
        lambda b, c: detect_numeric_distribution_shift(b, c, threshold=dist_threshold),
    ]


def _apply_precedence(symptoms: list):
    """Drop symptoms that a more specific co-located signature has superseded."""
    suppressed: set[tuple[str, str]] = set()
    for s in symptoms:
        for victim in _SUPPRESSES.get(s.signature, ()):
            suppressed.add((s.column, victim))
    return [s for s in symptoms if (s.column, s.signature) not in suppressed]


def detect_symptoms_from_profiles(
    before: dict[str, ColumnProfile],
    after: dict[str, ColumnProfile],
    columns: list[str] | None = None,
    *,
    dist_threshold: float = DEFAULT_DISTRIBUTION_THRESHOLD,
    model: LogisticModel | None = None,
):
    """Run every active detector over already-computed profiles.

    This is the shared detection core: both the local Polars path and the
    warehouse pushdown path funnel through here, so they cannot diverge.
    """
    if columns is None:
        columns = [c for c in before if c in after]

    detectors = _build_detectors(dist_threshold)
    symptoms = []
    for column in columns:
        baseline, current = before[column], after[column]
        for detector in detectors:
            symptom = detector(baseline, current)
            if symptom is not None:
                symptoms.append(symptom)

    survivors = _apply_precedence(symptoms)
    if model is not None:
        survivors = [
            attach_confidence(s, before[s.column], after[s.column], model)
            for s in survivors
        ]
    return survivors


def detect_symptoms(
    before: pl.DataFrame,
    after: pl.DataFrame,
    columns: list[str] | None = None,
    *,
    dist_threshold: float = DEFAULT_DISTRIBUTION_THRESHOLD,
    model: LogisticModel | None = None,
):
    """Profile the given columns before/after and run every active detector.

    When ``model`` is supplied, each surviving symptom is annotated with a
    measured ``confidence``; otherwise ``confidence`` stays ``None`` (M1/M2
    behavior unchanged).
    """
    if columns is None:
        columns = [c for c in before.columns if c in after.columns]

    before_profiles = {c: profile_column(before[c].rename(c)) for c in columns}
    after_profiles = {c: profile_column(after[c].rename(c)) for c in columns}
    return detect_symptoms_from_profiles(
        before_profiles, after_profiles, columns,
        dist_threshold=dist_threshold, model=model,
    )


def analyze_change(
    *,
    asset: str,
    before: pl.DataFrame,
    after: pl.DataFrame,
    observed_at: datetime,
    lineage: LineageGraph,
    changes: list[ChangeEvent],
    columns: list[str] | None = None,
    model: LogisticModel | None = None,
) -> Incident | None:
    """Analyze a before/after snapshot of one asset and return an incident.

    Returns ``None`` when either no signature fires or nothing corroborates the
    symptoms into an incident. When ``model`` is supplied, the incident carries a
    measured confidence for its primary symptom.
    """
    symptoms = detect_symptoms(before, after, columns, model=model)
    if not symptoms:
        return None

    observations = [Observation(asset, observed_at, s) for s in symptoms]
    ranked = rank_root_causes(observations, changes, lineage)
    return synthesize_incident(ranked, lineage, observations)


def analyze_change_from_profiles(
    *,
    asset: str,
    before: dict[str, ColumnProfile],
    after: dict[str, ColumnProfile],
    observed_at: datetime,
    lineage: LineageGraph,
    changes: list[ChangeEvent],
    columns: list[str] | None = None,
    model: LogisticModel | None = None,
) -> Incident | None:
    """Analyze a before/after pair of column profiles and return an incident.

    The warehouse-pushdown twin of :func:`analyze_change`: it takes profiles
    already computed in-warehouse instead of raw DataFrames, then runs the
    identical detection / attribution / synthesis path.
    """
    symptoms = detect_symptoms_from_profiles(before, after, columns, model=model)
    if not symptoms:
        return None

    observations = [Observation(asset, observed_at, s) for s in symptoms]
    ranked = rank_root_causes(observations, changes, lineage)
    return synthesize_incident(ranked, lineage, observations)
