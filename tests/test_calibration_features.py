"""Feature extraction for the per-symptom calibration model."""

import math

from dvi.calibration.features import FEATURE_NAMES, extract_features
from dvi.detection import (
    detect_numeric_distribution_shift,
    detect_value_substitution,
)
from dvi.profiling import ColumnProfile, NumericStats


def _cat(name: str, top_k: dict[str, int]) -> ColumnProfile:
    row_count = sum(top_k.values())
    return ColumnProfile(
        name=name,
        row_count=row_count,
        null_count=0,
        distinct_count=len(top_k),
        top_k=top_k,
    )


def _scaled(shares: dict[str, float], n: int) -> dict[str, int]:
    return {k: round(v * n) for k, v in shares.items()}


def _num(name: str, qs: dict[str, float], n: int = 1000) -> ColumnProfile:
    return ColumnProfile(
        name=name,
        row_count=n,
        null_count=0,
        distinct_count=n,
        numeric=NumericStats(
            count=n,
            mean=qs["p50"],
            stddev=(qs["p95"] - qs["p05"]) / 3.29,
            minimum=qs["p05"],
            maximum=qs["p95"],
            quantiles=qs,
        ),
    )


_SUBST_BEFORE = {"A": 0.5, "B": 0.3, "C": 0.2}
_SUBST_AFTER = {"A": 0.5, "B": 0.1, "C": 0.2, "D": 0.2}


def _substitution_features(n: int):
    baseline = _cat("region", _scaled(_SUBST_BEFORE, n))
    current = _cat("region", _scaled(_SUBST_AFTER, n))
    symptom = detect_value_substitution(baseline, current)
    assert symptom is not None
    return extract_features(symptom, baseline, current)


def test_feature_vector_has_the_three_named_features_in_order():
    fv = _substitution_features(1000)
    assert FEATURE_NAMES == ["magnitude", "significance_margin", "log10_n"]
    assert fv.as_list() == [fv.magnitude, fv.significance_margin, fv.log10_n]


def test_substitution_features_are_sensible():
    fv = _substitution_features(1000)
    # ~20% of mass relocated.
    assert 0.15 <= fv.magnitude <= 0.25
    # A clean 20-point move on 1000 rows is far above sampling noise.
    assert fv.significance_margin > 1.0
    # log10(1000) == 3.
    assert abs(fv.log10_n - 3.0) < 1e-9


def test_significance_margin_grows_with_sample_size():
    small = _substitution_features(300)
    large = _substitution_features(30_000)
    # Same effect size, more rows -> more significant.
    assert large.significance_margin > small.significance_margin


def test_numeric_features_use_threshold_margin():
    baseline = _num("amount", {"p05": 10, "p25": 20, "p50": 30, "p75": 40, "p95": 50})
    current = _num("amount", {"p05": 20, "p25": 30, "p50": 40, "p75": 50, "p95": 60})
    symptom = detect_numeric_distribution_shift(baseline, current)
    assert symptom is not None

    fv = extract_features(symptom, baseline, current)
    # A +10 shift on a 40-wide spread is well beyond the 0.10 threshold.
    assert fv.significance_margin > 1.0
    assert not math.isnan(fv.significance_margin)


def _numeric_shift_features(n: int):
    # +10 shift on a 40-wide spread -> normalized distance 0.25, above 0.10.
    baseline = _num("amount", {"p05": 10, "p25": 20, "p50": 30, "p75": 40, "p95": 50}, n=n)
    current = _num("amount", {"p05": 20, "p25": 30, "p50": 40, "p75": 50, "p95": 60}, n=n)
    symptom = detect_numeric_distribution_shift(baseline, current)
    assert symptom is not None
    return extract_features(symptom, baseline, current)


def test_numeric_significance_margin_is_sample_size_aware():
    # The detector's firing gate is max(fixed threshold, sample-size noise floor),
    # so the margin must divide the same distance by that effective bar: identical
    # normalized distance is less significant at small n (the noise floor dominates)
    # than at large n (the fixed threshold dominates).
    small = _numeric_shift_features(40)
    large = _numeric_shift_features(50_000)
    assert large.significance_margin > small.significance_margin
