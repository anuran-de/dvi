"""The sample-size-aware significance guard on the share-based signatures.

Motivation (from real-data validation): running two random halves of the *same*
dataset through the share-based detectors false-fired constantly at small sample
sizes, because a flat share-shift floor (``MIN_SHIFT``) cannot tell a genuine
relocation from ordinary sampling noise. The guard raises the per-value floor to
``max(MIN_SHIFT, Z * standard_error)`` so the *same* share move is noise at small
n and signal at large n.
"""

from dvi.detection import (
    Symptom,
    detect_category_split_merge,
    detect_value_substitution,
)
from dvi.profiling import ColumnProfile


def _profile(name: str, top_k: dict[str, int], nulls: int = 0) -> ColumnProfile:
    row_count = sum(top_k.values()) + nulls
    return ColumnProfile(
        name=name,
        row_count=row_count,
        null_count=nulls,
        distinct_count=len(top_k),
        top_k=top_k,
    )


def _scaled(top_k_shares: dict[str, float], n: int) -> dict[str, int]:
    """Turn a share map into integer counts summing to ``n``."""
    return {value: round(share * n) for value, share in top_k_shares.items()}


# A clean 4-point relocation B -> D. At 250 rows this is within sampling noise;
# at 10k rows it is unambiguous. Shares are identical at both sizes.
_SUBST_BEFORE = {"A": 0.50, "B": 0.30, "C": 0.20}
_SUBST_AFTER = {"A": 0.50, "B": 0.26, "C": 0.20, "D": 0.04}


def test_value_substitution_suppressed_at_small_sample():
    baseline = _profile("region", _scaled(_SUBST_BEFORE, 250))
    current = _profile("region", _scaled(_SUBST_AFTER, 250))

    # A 4-point move on 250 rows is inside the sampling-noise band -> silent.
    assert detect_value_substitution(baseline, current) is None


def test_value_substitution_fires_at_large_sample():
    baseline = _profile("region", _scaled(_SUBST_BEFORE, 10_000))
    current = _profile("region", _scaled(_SUBST_AFTER, 10_000))

    symptom = detect_value_substitution(baseline, current)

    assert isinstance(symptom, Symptom)
    assert symptom.from_value == "B"
    assert symptom.to_value == "D"


# A small split B -> {B, D, E}. Noise at 200 rows, signal at 20k.
_SPLIT_BEFORE = {"A": 0.70, "B": 0.30}
_SPLIT_AFTER = {"A": 0.70, "B": 0.24, "D": 0.03, "E": 0.03}


def test_split_suppressed_at_small_sample():
    baseline = _profile("category", _scaled(_SPLIT_BEFORE, 200))
    current = _profile("category", _scaled(_SPLIT_AFTER, 200))

    assert detect_category_split_merge(baseline, current) is None


def test_split_fires_at_large_sample():
    baseline = _profile("category", _scaled(_SPLIT_BEFORE, 20_000))
    current = _profile("category", _scaled(_SPLIT_AFTER, 20_000))

    symptom = detect_category_split_merge(baseline, current)

    assert isinstance(symptom, Symptom)
    assert symptom.evidence["kind"] == "split"
