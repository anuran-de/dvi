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

from dvi.profiling import ColumnProfile

from .symptom import Symptom

_QUANTILE_KEYS = ["p05", "p25", "p50", "p75", "p95"]
DEFAULT_THRESHOLD = 0.1


def _baseline_scale(quantiles: dict[str, float], stddev: float) -> float | None:
    spread = quantiles.get("p95", 0.0) - quantiles.get("p05", 0.0)
    if spread > 0:
        return spread
    if stddev > 0:
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
    if scale is None:
        return None
    if not all(k in b.quantiles and k in c.quantiles for k in _QUANTILE_KEYS):
        return None

    distance = (
        sum(abs(c.quantiles[k] - b.quantiles[k]) for k in _QUANTILE_KEYS)
        / len(_QUANTILE_KEYS)
        / scale
    )
    if distance < threshold:
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
