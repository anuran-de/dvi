"""Signature #3 — category split/merge.

One category fans out into several (``"Electronics"`` -> ``"Consumer Electronics"``
+ ``"Home Electronics"``), or several collapse into one. The distinct-count
changes and, unlike a one-to-one substitution (#1), the mass of a single category
is conserved across a *set* of new categories rather than a single replacement.

We identify the categories that lost share and those that gained it, then look for
a one-to-many (split) or many-to-one (merge) shape whose total lost and gained
mass are conserved. The 1-to-1 shape is deliberately excluded — that is #1's job.
"""

from __future__ import annotations

from dvi.profiling import ColumnProfile

from .significance import noise_threshold, pooled_share
from .symptom import Symptom

MIN_SHARE = 0.03
MIN_SHIFT = 0.02
MIN_TOP_K_COVERAGE = 0.9
# Total lost and gained mass must match this closely to read as a redistribution.
CONSERVE_TOL = 0.15


def _coverage(profile: ColumnProfile) -> float:
    if profile.non_null_count == 0:
        return 0.0
    return sum(profile.top_k.values()) / profile.non_null_count


def detect_category_split_merge(
    baseline: ColumnProfile, current: ColumnProfile
) -> Symptom | None:
    """Return a Symptom if one category split into many or many merged into one."""
    if not baseline.top_k or not current.top_k:
        return None
    if _coverage(baseline) < MIN_TOP_K_COVERAGE or _coverage(current) < MIN_TOP_K_COVERAGE:
        return None

    values = set(baseline.top_k) | set(current.top_k)
    na, nb = baseline.non_null_count, current.non_null_count
    dropped: list[tuple[str, float]] = []
    gained: list[tuple[str, float]] = []
    for value in values:
        base_share = baseline.value_share(value)
        curr_share = current.value_share(value)
        delta = curr_share - base_share
        # Sample-size-aware floor: a share move must clear sampling noise, not
        # just the fixed relevance floor. Each split fragment is checked on its
        # own, so noise-sized fragments never fabricate a split. The SE uses the
        # count-weighted pooled proportion.
        p = pooled_share(base_share, curr_share, na, nb)
        shift_floor = max(MIN_SHIFT, noise_threshold(p, na, nb))
        if delta <= -shift_floor and base_share >= MIN_SHARE:
            dropped.append((value, -delta))
        elif delta >= shift_floor and curr_share >= MIN_SHARE:
            gained.append((value, delta))

    if len(dropped) == 1 and len(gained) >= 2:
        kind = "split"
        sources, targets = dropped, gained
    elif len(gained) == 1 and len(dropped) >= 2:
        kind = "merge"
        sources, targets = dropped, gained
    else:
        # Includes the 1-to-1 (substitution) and ambiguous many-to-many shapes.
        return None

    lost_total = sum(share for _, share in dropped)
    gained_total = sum(share for _, share in gained)
    if min(lost_total, gained_total) / max(lost_total, gained_total) < (1.0 - CONSERVE_TOL):
        return None

    # Order members by share (desc), lexicographic tie-break, for determinism.
    src_names = [v for v, _ in sorted(sources, key=lambda i: (-i[1], i[0]))]
    tgt_names = [v for v, _ in sorted(targets, key=lambda i: (-i[1], i[0]))]

    if kind == "split":
        from_value, to_value = src_names[0], " + ".join(tgt_names)
    else:
        from_value, to_value = " + ".join(src_names), tgt_names[0]

    magnitude = min(1.0, (lost_total + gained_total) / 2.0)
    return Symptom(
        signature="category_split_merge",
        column=baseline.name,
        magnitude=magnitude,
        from_value=from_value,
        to_value=to_value,
        description=(
            f"Category {kind} in {baseline.name!r}: {from_value!r} -> {to_value!r} "
            f"({magnitude:.1%} of the distribution redistributed)."
        ),
        evidence={
            "kind": kind,
            "sources": src_names,
            "targets": tgt_names,
            "lost_total": round(lost_total, 4),
            "gained_total": round(gained_total, 4),
        },
    )
