"""Signature #1 — value substitution.

Recognises the fingerprint of a categorical value being *renamed/replaced*: one
value's share of the distribution collapses while a previously-absent (or rare)
value gains almost exactly that share, with the overall proportions otherwise
conserved. This is the ``"UK" -> "United Kingdom"`` / ``"completed" -> "COMPLETE"``
class of change — invisible to schema, volume, freshness and null checks.

The test is fully deterministic and works on *shares* (fractions of non-null
rows), so a proportional change in volume alone never triggers it.
"""

from __future__ import annotations

from dvi.profiling import ColumnProfile

from .significance import noise_threshold, pooled_share
from .symptom import Symptom

# A value must hold at least this share to be considered a real category
# (filters high-cardinality noise / one-off flickering values).
MIN_SHARE = 0.03
# The share must move by at least this much to count as a drop/gain.
MIN_SHIFT = 0.02
# Lost and gained mass must match this closely to be read as a single relocation.
# min(lost, gained) / max(lost, gained) must be >= (1 - MASS_MATCH_TOL).
MASS_MATCH_TOL = 0.35
# The retained top_k must cover at least this fraction of non-null rows. Below
# this, the column is too long-tailed/high-cardinality for the top_k profile to
# be trustworthy: a value dropping out of top_k would look like a phantom drop.
MIN_TOP_K_COVERAGE = 0.9


def _coverage(profile: ColumnProfile) -> float:
    """Fraction of non-null rows represented by the retained top_k values."""
    if profile.non_null_count == 0:
        return 0.0
    return sum(profile.top_k.values()) / profile.non_null_count


def detect_value_substitution(
    baseline: ColumnProfile, current: ColumnProfile
) -> Symptom | None:
    """Return a Symptom if a mass-conserving value substitution is detected."""
    if (
        _coverage(baseline) < MIN_TOP_K_COVERAGE
        or _coverage(current) < MIN_TOP_K_COVERAGE
    ):
        return None

    values = set(baseline.top_k) | set(current.top_k)
    na, nb = baseline.non_null_count, current.non_null_count

    dropped: list[tuple[str, float]] = []
    gained: list[tuple[str, float]] = []
    for value in values:
        base_share = baseline.value_share(value)
        curr_share = current.value_share(value)
        delta = curr_share - base_share
        # A share move counts only if it clears both the fixed relevance floor
        # and the sample-size-aware noise floor (a small move on few rows is
        # indistinguishable from sampling noise; the same move on many rows is
        # real). The SE uses the count-weighted pooled proportion.
        p = pooled_share(base_share, curr_share, na, nb)
        shift_floor = max(MIN_SHIFT, noise_threshold(p, na, nb))
        if delta <= -shift_floor and base_share >= MIN_SHARE:
            dropped.append((value, -delta))
        elif delta >= shift_floor and curr_share >= MIN_SHARE:
            gained.append((value, delta))

    if not dropped or not gained:
        return None

    # A one-to-many / many-to-one redistribution is a split/merge (signature #3's
    # domain), not a 1-to-1 substitution. The significance floor above has already
    # removed noise-sized movers, so ≥2 real movers on one side means a genuine
    # split/merge — defer to #3 rather than mislabel the largest pair as a rename.
    if (len(dropped) == 1 and len(gained) >= 2) or (len(gained) == 1 and len(dropped) >= 2):
        return None

    # Match the largest drop to the gain whose mass is closest to it. Ties are
    # broken lexicographically so the result is deterministic regardless of
    # set/hash iteration order.
    from_value, lost = min(dropped, key=lambda item: (-item[1], item[0]))
    to_value, best_gain = min(
        gained, key=lambda item: (abs(item[1] - lost), item[0])
    )

    if min(lost, best_gain) / max(lost, best_gain) < (1.0 - MASS_MATCH_TOL):
        return None

    magnitude = (lost + best_gain) / 2.0
    return Symptom(
        signature="value_substitution",
        column=baseline.name,
        magnitude=magnitude,
        from_value=from_value,
        to_value=to_value,
        description=(
            f"Value {from_value!r} ({lost:.1%} of the distribution) appears "
            f"replaced by {to_value!r} ({best_gain:.1%})."
        ),
        evidence={
            "from_value": from_value,
            "from_share_lost": round(lost, 4),
            "to_value": to_value,
            "to_share_gained": round(best_gain, 4),
            "mass_match": round(min(lost, best_gain) / max(lost, best_gain), 4),
        },
    )
