"""Measure whether the confidence numbers are honest.

A confidence is only meaningful if it is *calibrated*: of the symptoms scored
0.7, about 70% should be real. We check that with a reliability table built from
**out-of-fold** predictions — every row is scored by a model that never saw it —
and summarise the gap with the Expected Calibration Error and the Brier score.

No plotting library is available, so the "diagram" is a text/markdown table with
per-bin counts (sparse bins stay visible instead of being hidden by a curve).
"""

from __future__ import annotations

from dataclasses import dataclass

from .dataset import LabeledSymptom
from .model import LogisticModel

# Defaults for the cross-validated fit. Light L2 keeps the fit honest (a zero-L2
# fit lands near-perfect on this near-separable set, which reads as overfit rather
# than calibrated); tuned so out-of-fold ECE sits low without collapsing to 0/1.
_DEFAULT_L2 = 0.01
_DEFAULT_LR = 0.3
_DEFAULT_ITERS = 3000

Pair = tuple[float, int]


@dataclass(frozen=True)
class ReliabilityBin:
    """One probability bin of the reliability table."""

    lo: float
    hi: float
    count: int
    predicted: float
    empirical: float

    @property
    def gap(self) -> float:
        return abs(self.predicted - self.empirical)


@dataclass(frozen=True)
class ReliabilityReport:
    """The reliability table plus its scalar calibration summaries.

    ``ece`` is count-weighted, so on a near-separable set (most predictions in the
    0–0.1 and 0.9–1.0 bins) it is dominated by the well-separated extremes and
    reports how well the model *ranks* real vs noise. ``mce`` — the worst single
    populated-bin gap — is the honest companion: it surfaces mid-range bins the
    ECE average hides, and is the number to watch for intermediate-probability
    calibration.
    """

    bins: list[ReliabilityBin]
    ece: float
    mce: float
    brier: float
    count: int
    positives: int

    @property
    def mid_range_count(self) -> int:
        """Predictions in the intermediate [0.2, 0.8] band (calibration is only
        meaningfully *tested* where bins are populated)."""
        return sum(b.count for b in self.bins if b.lo >= 0.2 and b.hi <= 0.8)


def assign_folds(n: int, k: int) -> list[int]:
    """Deterministic fold id per row index (``index % k``)."""
    return [i % k for i in range(n)]


def brier_score(pairs: list[Pair]) -> float:
    """Mean squared error between predicted probability and outcome."""
    if not pairs:
        return 0.0
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs)


def _bin_index(p: float, bins: int) -> int:
    return min(bins - 1, max(0, int(p * bins)))


def reliability_table(pairs: list[Pair], bins: int = 10) -> list[ReliabilityBin]:
    """Equal-width bins over [0, 1] with per-bin count, mean predicted, empirical."""
    buckets: list[list[Pair]] = [[] for _ in range(bins)]
    for p, y in pairs:
        buckets[_bin_index(p, bins)].append((p, y))

    table: list[ReliabilityBin] = []
    for b in range(bins):
        items = buckets[b]
        count = len(items)
        predicted = sum(p for p, _ in items) / count if count else 0.0
        empirical = sum(y for _, y in items) / count if count else 0.0
        table.append(ReliabilityBin(b / bins, (b + 1) / bins, count, predicted, empirical))
    return table


def expected_calibration_error(pairs: list[Pair], bins: int = 10) -> float:
    """Count-weighted average gap between predicted and empirical frequency."""
    if not pairs:
        return 0.0
    n = len(pairs)
    return sum(b.count / n * b.gap for b in reliability_table(pairs, bins) if b.count)


def max_calibration_error(pairs: list[Pair], bins: int = 10) -> float:
    """Worst single populated-bin gap between predicted and empirical frequency.

    Unlike the count-weighted ECE, this is not diluted by heavily-populated,
    well-calibrated extreme bins, so it exposes mid-range miscalibration.
    """
    if not pairs:
        return 0.0
    return max((b.gap for b in reliability_table(pairs, bins) if b.count), default=0.0)


def build_reliability_report(pairs: list[Pair], bins: int = 10) -> ReliabilityReport:
    """Bundle the table with ECE, MCE, Brier and totals."""
    return ReliabilityReport(
        bins=reliability_table(pairs, bins),
        ece=expected_calibration_error(pairs, bins),
        mce=max_calibration_error(pairs, bins),
        brier=brier_score(pairs),
        count=len(pairs),
        positives=sum(y for _, y in pairs),
    )


def k_fold_predictions(
    dataset: list[LabeledSymptom],
    k: int = 5,
    *,
    seed: int = 0,
    l2: float = _DEFAULT_L2,
    lr: float = _DEFAULT_LR,
    iters: int = _DEFAULT_ITERS,
) -> list[Pair]:
    """Pooled out-of-fold ``(prob, label)`` predictions.

    Each fold is held out, a model is fit on the rest, and the held-out rows are
    scored by that model — so no row is ever scored by a model that trained on it.
    """
    n = len(dataset)
    folds = assign_folds(n, k)
    X = [s.features.as_list() for s in dataset]
    y = [s.label for s in dataset]

    predictions: list[Pair | None] = [None] * n
    for f in range(k):
        train = [i for i in range(n) if folds[i] != f]
        test = [i for i in range(n) if folds[i] == f]
        if not test or not train:
            continue
        model = LogisticModel.fit(
            [X[i] for i in train], [y[i] for i in train], l2=l2, lr=lr, iters=iters
        )
        for i, prob in zip(test, model.predict_proba([X[i] for i in test]), strict=True):
            predictions[i] = (prob, y[i])

    return [p for p in predictions if p is not None]


def render_reliability(report: ReliabilityReport) -> str:
    """A markdown reliability table with per-bin counts; no plotting."""
    lines = [
        f"Reliability (n={report.count}, positives={report.positives})",
        "| bin | n | predicted | empirical | gap |",
        "|-----|---|-----------|-----------|-----|",
    ]
    for b in report.bins:
        if b.count == 0:
            continue
        lines.append(
            f"| {b.lo:.1f}-{b.hi:.1f} | {b.count} | {b.predicted:.3f} | "
            f"{b.empirical:.3f} | {b.gap:.3f} |"
        )
    lines.append(
        f"ECE = {report.ece:.4f}   MCE = {report.mce:.4f}   Brier = {report.brier:.4f}"
    )
    lines.append(
        f"(ECE is count-weighted, dominated by the extremes; MCE is the worst bin. "
        f"{report.mid_range_count} of {report.count} predictions land in [0.2, 0.8].)"
    )
    return "\n".join(lines)
