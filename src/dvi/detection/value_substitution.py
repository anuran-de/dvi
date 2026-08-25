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

from .symptom import Symptom

# A value must hold at least this share to be considered a real category
# (filters high-cardinality noise / one-off flickering values).
MIN_SHARE = 0.03
# The share must move by at least this much to count as a drop/gain.
MIN_SHIFT = 0.02
# Lost and gained mass must match this closely to be read as a single relocation.
# min(lost, gained) / max(lost, gained) must be >= (1 - MASS_MATCH_TOL).
MASS_MATCH_TOL = 0.35


def detect_value_substitution(
    baseline: ColumnProfile, current: ColumnProfile
) -> Symptom | None:
    """Return a Symptom if a mass-conserving value substitution is detected."""
    values = set(baseline.top_k) | set(current.top_k)

    dropped: list[tuple[str, float]] = []
    gained: list[tuple[str, float]] = []
    for value in values:
        base_share = baseline.value_share(value)
        curr_share = current.value_share(value)
        delta = curr_share - base_share
        if delta <= -MIN_SHIFT and base_share >= MIN_SHARE:
            dropped.append((value, -delta))
        elif delta >= MIN_SHIFT and curr_share >= MIN_SHARE:
            gained.append((value, delta))

    if not dropped or not gained:
        return None

    # Match the largest drop to the gain whose mass is closest to it.
    from_value, lost = max(dropped, key=lambda item: item[1])
    to_value, best_gain = min(
        gained, key=lambda item: abs(item[1] - lost)
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
