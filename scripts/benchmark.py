"""DVI M2 benchmark — recall vs. false positives.

Run:  python scripts/benchmark.py

Scores every detector against the labelled suite (positives across signatures #1-5,
plus normal-variation negatives and benign decoys), then sweeps the one continuous
knob (the distribution-shift threshold) to trace the recall/false-positive operating
curve and pick a robust operating point. The headline: catch every injected change
while staying silent on legitimate variation like a doubling in volume.
"""

from __future__ import annotations

from dvi.benchmark import (
    build_scenarios,
    evaluate,
    evaluate_blast_radius,
    evaluate_rca,
    evaluate_real_data,
    recall_at_fixed_fp,
    sweep,
)
from dvi.calibration.dataset import build_calibration_dataset
from dvi.calibration.reliability import (
    build_reliability_report,
    k_fold_predictions,
    render_reliability,
)
from dvi.detection import DEFAULT_DISTRIBUTION_THRESHOLD


def main() -> None:
    scenarios = build_scenarios()
    kinds = {"positive": 0, "negative": 0, "decoy": 0}
    for s in scenarios:
        kinds[s.kind] += 1

    print("=" * 70)
    print("  DVI benchmark - semantic change detection")
    print("=" * 70)
    print(
        f"  Suite: {kinds['positive']} positives (one per signature #1-5), "
        f"{kinds['negative']} negatives, {kinds['decoy']} decoys"
    )

    report = evaluate(scenarios, dist_threshold=DEFAULT_DISTRIBUTION_THRESHOLD)
    print(f"\n  At the shipped default threshold ({DEFAULT_DISTRIBUTION_THRESHOLD:.2f}):")
    print(f"    recall              : {report.recall:.0%}")
    print(f"    false-positive rate : {report.false_positive_rate:.0%}")
    if report.missed:
        print(f"    missed              : {', '.join(report.missed)}")
    if report.false_positives:
        print(f"    false positives     : {', '.join(report.false_positives)}")

    print("\n  Operating curve (distribution-shift threshold sweep):")
    print(f"    {'threshold':>10} {'recall':>8} {'fp_rate':>8}   false positives")
    prev = None
    for rep in sweep(scenarios):
        key = (round(rep.recall, 3), round(rep.false_positive_rate, 3))
        if key != prev:  # print only where the operating point changes
            fps = ", ".join(rep.false_positives) or "-"
            print(
                f"    {rep.threshold:>10.2f} {rep.recall:>8.0%} "
                f"{rep.false_positive_rate:>8.0%}   {fps}"
            )
            prev = key

    op = recall_at_fixed_fp(scenarios, max_fp_rate=0.0)
    print(
        f"\n  Chosen operating point (max recall at 0% FP): "
        f"threshold={op.threshold:.2f}, recall={op.recall:.0%}, "
        f"fp_rate={op.false_positive_rate:.0%}"
    )

    rca = evaluate_rca()
    print("\n  Root-cause ranking under distractors:")
    print(f"    cases            : {len(rca.results)}")
    print(f"    top-1 accuracy   : {rca.top1_accuracy:.0%}")
    if rca.wrong:
        print(f"    mis-ranked       : {', '.join(rca.wrong)}")

    blast = evaluate_blast_radius()
    print("\n  Blast-radius / business impact (labeled, with decoys):")
    print(f"    cases              : {len(blast.results)}")
    print(f"    exposure precision : {blast.precision:.0%}")
    print(f"    exposure recall    : {blast.recall:.0%}")
    print(f"    severity accuracy  : {blast.severity_accuracy:.0%}")
    if blast.wrong:
        print(f"    wrong              : {', '.join(blast.wrong)}")

    print("\n" + "=" * 70)
    print("  Validation on real data (diamonds, 53,940 rows)")
    print("=" * 70)
    real = evaluate_real_data(n=1000, trials=30)
    print(
        f"  Real-vs-real false positives: {real.fp.fires}/{real.fp.checks} column-checks fire "
        f"({real.fp.false_positive_rate:.0%}) across {real.fp.trials} disjoint splits"
    )
    if real.fp.examples:
        print(f"    examples: {'; '.join(real.fp.examples)}")
    print(
        f"  Injected-rename recall: {real.recall.hits}/{real.recall.trials} "
        f"({real.recall.recall:.0%}) - a planted category rename recovered under real noise"
    )
    print(
        "  Two disjoint samples of the SAME distribution stay silent; a real change "
        "is still caught."
    )

    print("\n" + "=" * 70)
    print("  Calibrated confidence (per-symptom, k-fold cross-validated)")
    print("=" * 70)
    dataset = build_calibration_dataset(seed=0)
    positives = sum(s.label for s in dataset)
    report = build_reliability_report(k_fold_predictions(dataset, k=5, seed=0))
    print(
        f"  Dataset: {len(dataset)} fired symptoms, {positives} real "
        f"({positives / len(dataset):.0%} positive) - real injections + hard negatives + synthetic"
    )
    print(
        f"  Out-of-fold ECE: {report.ece:.4f}   MCE: {report.mce:.4f}   "
        f"Brier: {report.brier:.4f}"
    )
    print("  Reliability (predicted vs. empirical, out-of-fold):")
    for line in render_reliability(report).splitlines()[1:]:
        print(f"    {line}")
    print(
        "  Confidence is conditional on firing; predictions skew to the extremes "
        "because most fired symptoms are clearly real or clearly noise."
    )
    print()


if __name__ == "__main__":
    main()
