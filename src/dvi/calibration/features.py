"""Turn a fired symptom into the 3-feature vector the confidence model scores.

The features are deliberately minimal and uniform. ``magnitude`` and ``log10_n``
are computed identically for every signature; only ``significance_margin``
branches, because "how far past the noise floor" means something different for a
categorical share move, a numeric quantile shift, and a unit/scale refit.

(A ``coverage`` feature was dropped: every fired categorical symptom already
clears the detectors' ``MIN_TOP_K_COVERAGE`` guard, so on the calibration set the
value was a constant 1.0 with zero variance and a trained weight of exactly 0 — a
dead input, not a signal. See docs/architecture.md §7.)

Everything is derived from the two ``ColumnProfile`` objects the detector already
saw, so the calibration layer never needs the raw data.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..detection.distribution_shift import DEFAULT_THRESHOLD as DISTRIBUTION_THRESHOLD
from ..detection.distribution_shift import _noise_floor as _distribution_noise_floor
from ..detection.significance import noise_threshold
from ..detection.symptom import Symptom
from ..detection.unit_scale_shift import ADD_TOLERANCE, MULT_TOLERANCE
from ..profiling import ColumnProfile

FEATURE_NAMES = ["magnitude", "significance_margin", "log10_n"]

# Categorical share signatures share one margin formula; numeric ones another.
_CATEGORICAL_SIGNATURES = frozenset(
    {"value_substitution", "category_split_merge", "case_format_normalization"}
)

# significance_margin is a ratio that can blow up when the noise floor is tiny;
# clip it so one near-noiseless symptom cannot dominate the standardization.
_MARGIN_CAP = 20.0


@dataclass(frozen=True)
class FeatureVector:
    """The 3 features scored by the confidence model, in a fixed order."""

    magnitude: float
    significance_margin: float
    log10_n: float

    def as_list(self) -> list[float]:
        return [self.magnitude, self.significance_margin, self.log10_n]


def _significance_margin(
    symptom: Symptom, baseline: ColumnProfile, current: ColumnProfile
) -> float:
    """Effect size in multiples of its noise/threshold floor, clipped."""
    na = baseline.non_null_count
    nb = current.non_null_count

    if symptom.signature in _CATEGORICAL_SIGNATURES:
        # The effect is the relocated/changed mass; its floor is the sampling
        # noise for a proportion of that size across the two samples.
        effect = symptom.magnitude
        floor = noise_threshold(effect, na, nb)
    elif symptom.signature == "numeric_distribution_shift":
        effect = float(symptom.evidence.get("normalized_distance", symptom.magnitude))
        # Divide by the SAME effective bar the detector fired against:
        # max(fixed threshold, sample-size noise floor). Using the flat constant
        # would overstate significance for a small-n shift the noise floor barely
        # let through. Use the numeric (finite-value) counts the detector used.
        nb_num = baseline.numeric.count if baseline.numeric else na
        nc_num = current.numeric.count if current.numeric else nb
        floor = max(DISTRIBUTION_THRESHOLD, _distribution_noise_floor(nb_num, nc_num))
    elif symptom.signature == "unit_scale_shift":
        effect = symptom.magnitude
        kind = symptom.evidence.get("kind")
        floor = MULT_TOLERANCE if kind == "multiplicative" else ADD_TOLERANCE
    else:
        effect = symptom.magnitude
        floor = 0.0

    if floor <= 0.0:
        return _MARGIN_CAP
    return min(_MARGIN_CAP, effect / floor)


def extract_features(
    symptom: Symptom, baseline: ColumnProfile, current: ColumnProfile
) -> FeatureVector:
    """Build the calibration feature vector for a fired symptom."""
    na = baseline.non_null_count
    nb = current.non_null_count
    log10_n = math.log10(max(1, min(na, nb)))

    return FeatureVector(
        magnitude=symptom.magnitude,
        significance_margin=_significance_margin(symptom, baseline, current),
        log10_n=log10_n,
    )
