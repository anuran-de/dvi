"""DVI M2 benchmark — recall vs. false positives.

Run:  python scripts/benchmark.py

Scores every detector against the labelled suite (positives across signatures #1-5,
plus normal-variation negatives and benign decoys), then sweeps the one continuous
knob (the distribution-shift threshold) to trace the recall/false-positive operating
curve and pick a robust operating point. The headline: catch every injected change
while staying silent on legitimate variation like a doubling in volume.
"""

from __future__ import annotations

from dvi.benchmark import build_scenarios, evaluate, recall_at_fixed_fp, sweep
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
    print()


if __name__ == "__main__":
    main()
