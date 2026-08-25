from dvi.benchmark import build_scenarios, evaluate, recall_at_fixed_fp
from dvi.detection import DEFAULT_DISTRIBUTION_THRESHOLD


def test_suite_has_positives_negatives_and_decoys():
    scenarios = build_scenarios()
    kinds = {}
    for s in scenarios:
        kinds[s.kind] = kinds.get(s.kind, 0) + 1

    assert kinds == {"positive": 5, "negative": 3, "decoy": 4}
    # One clean positive per signature (#1..#5).
    assert {s.signature for s in scenarios if s.is_positive} == {
        "value_substitution",
        "case_format_normalization",
        "category_split_merge",
        "numeric_distribution_shift",
        "unit_scale_shift",
    }


def test_detectors_separate_signal_from_noise_at_default_operating_point():
    scenarios = build_scenarios()

    report = evaluate(scenarios, dist_threshold=DEFAULT_DISTRIBUTION_THRESHOLD)

    # Every injected change is caught with its correct signature...
    assert report.recall == 1.0
    # ...and nothing fires on normal variation or benign decoys.
    assert report.false_positive_rate == 0.0
    assert report.false_positives == []


def test_lowering_threshold_makes_the_numeric_decoys_bite():
    scenarios = build_scenarios()

    strict = evaluate(scenarios, dist_threshold=DEFAULT_DISTRIBUTION_THRESHOLD)
    loose = evaluate(scenarios, dist_threshold=0.03)

    # The sub-threshold numeric decoys/negatives are exactly what a too-loose
    # threshold turns into false positives; the benchmark makes that visible.
    assert strict.false_positive_rate == 0.0
    assert loose.false_positive_rate > 0.0


def test_recall_at_fixed_fp_finds_the_clean_operating_point():
    scenarios = build_scenarios()

    op = recall_at_fixed_fp(scenarios, max_fp_rate=0.0)

    assert op.recall == 1.0
    assert op.false_positive_rate == 0.0
    # The clean point sits at or below the shipped default threshold.
    assert op.threshold >= DEFAULT_DISTRIBUTION_THRESHOLD
