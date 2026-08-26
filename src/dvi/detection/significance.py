"""Sample-size-aware significance for share-based signatures.

The categorical signatures compare *shares* (fractions of rows). A flat threshold
on a share change is wrong: at 250 rows a 3-point move is pure sampling noise, at
250k rows it is a real event. Validating on real data made this concrete — two
random halves of the *same* dataset tripped ``value_substitution`` on essentially
every split at small sample sizes, because the flat floor could not tell signal
from noise.

The fix is a noise floor that scales with sample size: a share move only counts
when it exceeds ``Z`` standard errors of the two-proportion sampling distribution.
``Z = 3`` (~99.7%) drove the real-data false-positive rate to zero across sample
sizes from 250 to 2000 while leaving injected changes fully detected.
"""

from __future__ import annotations

import math

# Standard-error multiplier. 3.0 ≈ 99.7% (three sigma): a share move must clear
# three standard errors of sampling noise before it is treated as a real change.
SIGNIFICANCE_Z = 3.0


def pooled_share(
    base_share: float,
    curr_share: float,
    n_baseline: int,
    n_current: int,
) -> float:
    """Count-weighted pooled proportion ``(x_a + x_b) / (n_a + n_b)``.

    This is the proportion the two-sample standard error is built around. The
    share midpoint ``(p_a + p_b) / 2`` only equals it when the samples are the
    same size; when they differ, weighting by row counts is the correct pool.
    Falls back to the midpoint when neither sample size is known.
    """
    total = n_baseline + n_current
    if total <= 0:
        return (base_share + curr_share) / 2.0
    return (base_share * n_baseline + curr_share * n_current) / total


def noise_threshold(
    pooled_share: float,
    n_baseline: int,
    n_current: int,
    z: float = SIGNIFICANCE_Z,
) -> float:
    """Return the smallest share change distinguishable from sampling noise.

    Uses the two-proportion standard error ``sqrt(p(1-p)(1/n_a + 1/n_b))`` scaled
    by ``z``. Returns 0.0 when either sample size is unknown (no noise floor).
    """
    if n_baseline <= 0 or n_current <= 0:
        return 0.0
    p = min(max(pooled_share, 0.0), 1.0)
    se = math.sqrt(p * (1.0 - p) * (1.0 / n_baseline + 1.0 / n_current))
    return z * se
