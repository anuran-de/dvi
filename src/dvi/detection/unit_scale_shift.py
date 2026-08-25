"""Signature #5 — unit/scale shift.

Catches systematic re-encodings of a numeric column: dollars silently become
cents (x100), a timezone offset shifts every timestamp by a constant, a metric
switches from fractions to percentages. These are *rigid* transforms — every row
moves by the same affine map ``current = a * baseline + b`` — which is what sets
them apart from a genuine behavioral distribution shift (#4), where the *shape*
of the distribution changes.

We fit the affine map from two robust anchors (p25, p75), then check that every
stored quantile lands on that line to within a tight tolerance. A clean fit plus
a non-trivial slope or intercept is the signature. Because a uniform shift is a
special case of #4, this signature is more specific and takes precedence: when it
fires on a column, the pipeline suppresses the distribution-shift symptom there.
"""

from __future__ import annotations

import math

from dvi.profiling import ColumnProfile

from .symptom import Symptom

_QUANTILE_KEYS = ["p05", "p25", "p50", "p75", "p95"]

# Max per-quantile residual (relative to the current spread) still counted as a
# clean affine fit. Above this the transform isn't rigid — it's a shape change.
FIT_TOLERANCE = 0.05
# Slope must differ from 1 by at least this to count as a real rescale.
MULT_TOLERANCE = 0.2
# Intercept, relative to the baseline spread, to count as a real offset.
ADD_TOLERANCE = 0.2


def detect_unit_scale_shift(
    baseline: ColumnProfile,
    current: ColumnProfile,
) -> Symptom | None:
    """Return a Symptom if ``current`` is a rigid affine re-encoding of ``baseline``."""
    b, c = baseline.numeric, current.numeric
    if b is None or c is None:
        return None
    if not all(k in b.quantiles and k in c.quantiles for k in _QUANTILE_KEYS):
        return None

    base_iqr = b.quantiles["p75"] - b.quantiles["p25"]
    base_scale = b.quantiles["p95"] - b.quantiles["p05"]
    curr_scale = c.quantiles["p95"] - c.quantiles["p05"]
    if base_iqr <= 0 or base_scale <= 0 or curr_scale <= 0:
        return None

    slope = (c.quantiles["p75"] - c.quantiles["p25"]) / base_iqr
    intercept = c.quantiles["p25"] - slope * b.quantiles["p25"]

    # Every quantile must land on the fitted line for the transform to be rigid.
    max_residual = max(
        abs(c.quantiles[k] - (slope * b.quantiles[k] + intercept)) for k in _QUANTILE_KEYS
    )
    if max_residual / curr_scale > FIT_TOLERANCE:
        return None

    mult_mag = abs(math.log10(slope)) if slope > 0 else 1.0
    add_mag = abs(intercept) / base_scale
    is_multiplicative = abs(slope - 1.0) >= MULT_TOLERANCE
    is_additive = add_mag >= ADD_TOLERANCE
    if not (is_multiplicative or is_additive):
        return None

    magnitude = min(1.0, max(mult_mag if is_multiplicative else 0.0, add_mag))

    if mult_mag >= add_mag:
        kind = "multiplicative"
        detail = f"values scaled by x{slope:.4g}"
    else:
        kind = "additive"
        detail = f"values offset by {intercept:+.4g}"

    return Symptom(
        signature="unit_scale_shift",
        column=baseline.name,
        magnitude=magnitude,
        description=(
            f"Column {baseline.name!r} was re-encoded ({kind}): {detail}. "
            f"Every quantile moved by the same affine map, so this is a unit/scale "
            f"change rather than a behavioral shift."
        ),
        evidence={
            "kind": kind,
            "factor": round(slope, 6),
            "offset": round(intercept, 6),
            "max_residual_ratio": round(max_residual / curr_scale, 4),
            "baseline_quantiles": b.quantiles,
            "current_quantiles": c.quantiles,
        },
    )
