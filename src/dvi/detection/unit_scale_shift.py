"""Signature #5 — unit/scale shift.

Catches systematic re-encodings of a numeric column: dollars silently become
cents (x100), a timezone offset shifts every timestamp by a constant, a metric
switches from fractions to percentages. These are *rigid* transforms — every row
moves by the same affine map ``current = a * baseline + b`` — which is what sets
them apart from a genuine behavioral distribution shift (#4), where the *shape*
of the distribution changes.

We test two *single-parameter* hypotheses independently rather than fitting slope
and intercept jointly:

- **multiplicative** (``current = factor * baseline``, through the origin): the
  spread scales by ``factor = curr_spread / base_spread``; every quantile must
  land on ``factor * baseline`` within tolerance.
- **additive** (``current = baseline + offset``, slope fixed at 1): the location
  shifts by ``offset = current.p50 - baseline.p50``; every quantile must land on
  ``baseline + offset`` within tolerance.

Fitting them jointly is what a naive affine regression does — and on a narrow-spread
column living far from zero (a percentage around 61, say) it turns pure sampling
jitter into a bogus "slope 0.93 + intercept +4" that cancels out over the data
range. Two separate one-parameter fits have no such collinearity: a scale that is
really a no-op reads as ``factor ≈ 1``, and a shift that is really a no-op reads as
``offset ≈ 0``. Because a uniform shift is a special case of #4, this signature is
more specific and takes precedence: when it fires on a column, the pipeline
suppresses the distribution-shift symptom there.
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
# A column whose spread is below this fraction of where it sits (|median|, floored
# at 1) is effectively constant: the additive test divides the offset by that tiny
# spread, so sub-percent jitter on a value pinned at ~61 clears ADD_TOLERANCE and
# fires a bogus "offset". Real re-encoded columns keep their spread, so this only
# suppresses the near-constant degenerate case; any genuine large move there is
# still caught by #4 (whose own spread floor is 1e-4, well below this).
NARROW_SPREAD_FLOOR = 1e-3


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

    base_scale = b.quantiles["p95"] - b.quantiles["p05"]
    curr_scale = c.quantiles["p95"] - c.quantiles["p05"]
    if base_scale <= 0 or curr_scale <= 0:
        return None

    # Effectively-constant column far from zero: spread is negligible next to where
    # the column lives, so the affine fit is dominated by jitter. Don't fire.
    location = max(abs(b.quantiles["p50"]), 1.0)
    if base_scale < NARROW_SPREAD_FLOOR * location:
        return None

    # Multiplicative hypothesis: current = factor * baseline (through the origin).
    # factor comes from the spread ratio, which is independent of where the data
    # sits, so it can't be corrupted by a large offset from zero.
    factor = curr_scale / base_scale
    mult_residual = max(
        abs(c.quantiles[k] - factor * b.quantiles[k]) for k in _QUANTILE_KEYS
    ) / curr_scale

    # Additive hypothesis: current = baseline + offset (slope fixed at 1).
    offset = c.quantiles["p50"] - b.quantiles["p50"]
    add_residual = max(
        abs(c.quantiles[k] - (b.quantiles[k] + offset)) for k in _QUANTILE_KEYS
    ) / curr_scale

    is_multiplicative = mult_residual <= FIT_TOLERANCE and abs(factor - 1.0) >= MULT_TOLERANCE
    is_additive = add_residual <= FIT_TOLERANCE and abs(offset) / base_scale >= ADD_TOLERANCE
    if not (is_multiplicative or is_additive):
        return None

    # If both hypotheses somehow fit, trust the one that fits more tightly.
    if is_multiplicative and (not is_additive or mult_residual <= add_residual):
        kind = "multiplicative"
        magnitude = min(1.0, abs(math.log10(factor)) if factor > 0 else 1.0)
        detail = f"values scaled by x{factor:.4g}"
        residual = mult_residual
    else:
        kind = "additive"
        magnitude = min(1.0, abs(offset) / base_scale)
        detail = f"values offset by {offset:+.4g}"
        residual = add_residual

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
            "factor": round(factor, 6),
            "offset": round(offset, 6),
            "max_residual_ratio": round(residual, 4),
            "baseline_quantiles": b.quantiles,
            "current_quantiles": c.quantiles,
        },
    )
