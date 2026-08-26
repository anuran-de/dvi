"""Signature #4 — numeric distribution shift.

Detects behavioral changes in a numeric column: the average order value jumps,
a spread fans out, a tail thickens. Works on the stored quantiles, so it needs
no raw data at detection time.

The shift is measured as the mean absolute quantile movement normalized by the
baseline's own spread (p95 - p05), making it scale-free and comparable across
columns. That normalized distance is the tunable threshold used to pick the
recall/false-positive operating point (see the benchmark).
"""

from __future__ import annotations

import math

from dvi.profiling import ColumnProfile

from .symptom import Symptom

_QUANTILE_KEYS = ["p05", "p25", "p50", "p75", "p95"]
DEFAULT_THRESHOLD = 0.1

# Sample-size floor. Sample quantiles are noisy at small n, so two random halves
# of the *same* population routinely clear a flat threshold — the very false
# positive the categorical significance guard fixed, still live for numerics until
# now. A sample quantile's sampling SD, expressed in spread (p95-p05) units, is
# ~C/sqrt(n) (the median's is ≈0.38/sqrt(n) under normality; the mean-abs quantile
# deviation is of the same order). We require the normalized distance to also clear
# NOISE_Z such SDs. The coefficient was calibrated on real diamonds real-vs-real
# splits: at n=250 residual false positives are rare and by n=1000 the fixed
# threshold dominates, matching the share-based guard's behavior.
QUANTILE_NOISE_Z = 3.0
_QUANTILE_NOISE_SD = 0.38  # sample-median SD in spread units at n=1, under normality


def _noise_floor(n_baseline: int, n_current: int) -> float:
    """Smallest normalized distance distinguishable from quantile sampling noise."""
    n = min(n_baseline, n_current)
    if n <= 0:
        return 0.0
    return QUANTILE_NOISE_Z * _QUANTILE_NOISE_SD / math.sqrt(n)


# A spread within this fraction of the column's magnitude is treated as an
# effectively-constant column: dividing by such a tiny spread turns sub-ULP
# jitter into a huge normalized distance. 1e-4 (0.01% of magnitude) is far below
# any real distribution's relative spread, so this never suppresses genuine drift.
_REL_SPREAD_EPS = 1e-4


def _baseline_scale(quantiles: dict[str, float], stddev: float) -> float | None:
    spread = quantiles.get("p95", 0.0) - quantiles.get("p05", 0.0)
    # Absolute floor relative to where the column sits (>= 1 so small-magnitude
    # columns are judged on an absolute 1e-6, not scaled below it).
    location = max(abs(quantiles.get("p50", 0.0)), 1.0)
    floor = _REL_SPREAD_EPS * location
    if spread > floor:
        return spread
    if stddev > floor:
        return stddev
    return None


def detect_numeric_distribution_shift(
    baseline: ColumnProfile,
    current: ColumnProfile,
    *,
    threshold: float = DEFAULT_THRESHOLD,
) -> Symptom | None:
    """Return a Symptom if the numeric distribution moved beyond ``threshold``."""
    b, c = baseline.numeric, current.numeric
    if b is None or c is None:
        return None

    scale = _baseline_scale(b.quantiles, b.stddev)
    if scale is None or not math.isfinite(scale):
        return None
    if not all(k in b.quantiles and k in c.quantiles for k in _QUANTILE_KEYS):
        return None
    # A non-finite quantile must not slip through: `distance < threshold` fails
    # open for NaN (nan < 0.1 is False) and would emit a magnitude-1.0 symptom.
    if not all(
        math.isfinite(b.quantiles[k]) and math.isfinite(c.quantiles[k]) for k in _QUANTILE_KEYS
    ):
        return None

    distance = (
        sum(abs(c.quantiles[k] - b.quantiles[k]) for k in _QUANTILE_KEYS)
        / len(_QUANTILE_KEYS)
        / scale
    )
    # A move counts only if it clears both the fixed relevance threshold and the
    # sample-size-aware noise floor (the same move is noise at small n, signal at
    # large n), mirroring the share-based significance guard.
    effective_threshold = max(threshold, _noise_floor(b.count, c.count))
    if distance < effective_threshold:
        return None

    magnitude = min(1.0, distance)
    median_shift = c.quantiles["p50"] - b.quantiles["p50"]
    return Symptom(
        signature="numeric_distribution_shift",
        column=baseline.name,
        magnitude=magnitude,
        description=(
            f"Distribution of {baseline.name!r} shifted "
            f"(median {b.quantiles['p50']:.3g} -> {c.quantiles['p50']:.3g}, "
            f"normalized distance {distance:.2f})."
        ),
        evidence={
            "normalized_distance": round(distance, 4),
            "median_shift": round(median_shift, 4),
            "baseline_quantiles": b.quantiles,
            "current_quantiles": c.quantiles,
        },
    )
