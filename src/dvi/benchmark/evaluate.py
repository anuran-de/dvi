"""Score the detectors against the labelled benchmark suite.

Produces the numbers that back the project's central claim: the detectors catch
injected semantic changes (recall) while staying silent on normal variation and
benign decoys (false-positive rate). ``recall_at_fixed_fp`` sweeps the one
continuous knob — the distribution-shift threshold — to pick an operating point
that holds the false-positive rate at or below a target while maximising recall.
"""

from __future__ import annotations

from dataclasses import dataclass

from dvi.detection import DEFAULT_DISTRIBUTION_THRESHOLD
from dvi.pipeline.analyze import detect_symptoms

from .scenarios import Scenario, build_scenarios


@dataclass(frozen=True)
class ScenarioResult:
    scenario: Scenario
    signatures: list[str]
    detected_correct: bool  # positive caught with the right signature+column
    fired: bool  # any symptom at all

    @property
    def ok(self) -> bool:
        """Classified as intended: positives caught, non-positives silent."""
        return self.detected_correct if self.scenario.is_positive else not self.fired


@dataclass(frozen=True)
class BenchmarkReport:
    threshold: float
    results: list[ScenarioResult]
    recall: float
    false_positive_rate: float

    @property
    def false_positives(self) -> list[str]:
        return [
            r.scenario.name
            for r in self.results
            if not r.scenario.is_positive and r.fired
        ]

    @property
    def missed(self) -> list[str]:
        return [
            r.scenario.name
            for r in self.results
            if r.scenario.is_positive and not r.detected_correct
        ]


@dataclass(frozen=True)
class OperatingPoint:
    threshold: float
    recall: float
    false_positive_rate: float


def _score(scenario: Scenario, dist_threshold: float) -> ScenarioResult:
    symptoms = detect_symptoms(
        scenario.before, scenario.after, scenario.columns, dist_threshold=dist_threshold
    )
    signatures = [s.signature for s in symptoms]
    detected_correct = any(
        s.signature == scenario.signature and s.column == scenario.column
        for s in symptoms
    )
    return ScenarioResult(scenario, signatures, detected_correct, fired=bool(symptoms))


def evaluate(
    scenarios: list[Scenario] | None = None,
    *,
    dist_threshold: float = DEFAULT_DISTRIBUTION_THRESHOLD,
) -> BenchmarkReport:
    """Run every detector over the suite and compute recall + false-positive rate."""
    if scenarios is None:
        scenarios = build_scenarios()

    results = [_score(s, dist_threshold) for s in scenarios]

    positives = [r for r in results if r.scenario.is_positive]
    non_positives = [r for r in results if not r.scenario.is_positive]

    recall = (
        sum(r.detected_correct for r in positives) / len(positives) if positives else 0.0
    )
    fp_rate = (
        sum(r.fired for r in non_positives) / len(non_positives) if non_positives else 0.0
    )
    return BenchmarkReport(dist_threshold, results, recall, fp_rate)


def _threshold_grid() -> list[float]:
    # 0.01 .. 0.60 in 0.01 steps (integer loop avoids float drift).
    return [n / 100 for n in range(1, 61)]


def sweep(
    scenarios: list[Scenario] | None = None,
    thresholds: list[float] | None = None,
) -> list[BenchmarkReport]:
    """Evaluate the suite across a grid of distribution-shift thresholds."""
    if scenarios is None:
        scenarios = build_scenarios()
    if thresholds is None:
        thresholds = _threshold_grid()
    return [evaluate(scenarios, dist_threshold=t) for t in thresholds]


def recall_at_fixed_fp(
    scenarios: list[Scenario] | None = None,
    *,
    max_fp_rate: float = 0.0,
    thresholds: list[float] | None = None,
) -> OperatingPoint:
    """Pick the operating point maximising recall while keeping FP <= target.

    Among thresholds that satisfy the FP ceiling and reach the best achievable
    recall, we return the *middle* of that safe band — the point with the most
    headroom on both sides, which is the robust choice for a shipped default. If
    no threshold meets the ceiling, we fall back to the lowest-FP point.
    """
    reports = sweep(scenarios, thresholds)

    safe = [r for r in reports if r.false_positive_rate <= max_fp_rate]
    if safe:
        best_recall = max(r.recall for r in safe)
        band = sorted(
            (r for r in safe if r.recall == best_recall),
            key=lambda r: r.threshold,
        )
        chosen = band[len(band) // 2]
    else:
        # No threshold meets the ceiling: take the least-bad point.
        chosen = min(
            reports, key=lambda r: (r.false_positive_rate, -r.recall, r.threshold)
        )

    return OperatingPoint(chosen.threshold, chosen.recall, chosen.false_positive_rate)
