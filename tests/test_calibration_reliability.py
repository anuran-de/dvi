"""Reliability diagram, ECE and Brier — the honesty check on the confidence model."""

from dvi.benchmark.real_data import load_diamonds
from dvi.calibration.dataset import build_calibration_dataset
from dvi.calibration.reliability import (
    assign_folds,
    brier_score,
    build_reliability_report,
    expected_calibration_error,
    k_fold_predictions,
    max_calibration_error,
    render_reliability,
)

# Hand-computed fixture (see test docstrings): ECE == Brier == 0.16.
_MIXED = [(0.2, 0), (0.2, 0), (0.2, 1), (0.8, 1), (0.8, 1)]


def test_brier_score_matches_hand_computation():
    # ((0.2-0)^2*2 + (0.2-1)^2 + (0.8-1)^2*2) / 5 = 0.8 / 5 = 0.16
    assert abs(brier_score(_MIXED) - 0.16) < 1e-9


def test_expected_calibration_error_matches_hand_computation():
    # bin[0.2]: pred 0.2, emp 1/3, gap .1333, w 3/5 -> .08
    # bin[0.8]: pred 0.8, emp 1.0, gap .2,     w 2/5 -> .08  => ECE .16
    assert abs(expected_calibration_error(_MIXED, bins=10) - 0.16) < 1e-9


def test_perfectly_calibrated_set_has_zero_ece():
    # 10 predictions at p=0.3 with exactly 3 positives -> empirical == predicted.
    pairs = [(0.3, 1)] * 3 + [(0.3, 0)] * 7
    assert expected_calibration_error(pairs, bins=10) < 1e-9


def test_max_calibration_error_is_the_worst_bin_gap():
    # bin[0.2] gap .1333, bin[0.8] gap .2 -> worst-bin (MCE) is .2, above ECE .16.
    mce = max_calibration_error(_MIXED, bins=10)
    assert abs(mce - 0.2) < 1e-9
    assert mce >= expected_calibration_error(_MIXED, bins=10)


def test_report_exposes_mce_and_render_shows_it():
    report = build_reliability_report(_MIXED, bins=10)
    assert abs(report.mce - 0.2) < 1e-9
    assert "MCE" in render_reliability(report)


def test_assign_folds_is_a_disjoint_cover():
    folds = assign_folds(23, 5)
    assert len(folds) == 23
    assert set(folds) == {0, 1, 2, 3, 4}
    # index % k assignment.
    assert folds[0] == 0 and folds[6] == 1


def test_reliability_report_bins_and_totals():
    report = build_reliability_report(_MIXED, bins=10)
    assert report.count == 5
    assert report.positives == 3
    # Only two bins are populated.
    populated = [b for b in report.bins if b.count > 0]
    assert len(populated) == 2
    assert abs(report.ece - 0.16) < 1e-9
    assert abs(report.brier - 0.16) < 1e-9


def test_render_reliability_is_a_readable_table():
    text = render_reliability(build_reliability_report(_MIXED, bins=10))
    assert "predicted" in text.lower()
    assert "empirical" in text.lower()
    assert "ECE" in text
    assert "Brier" in text


def test_k_fold_predictions_cover_every_row_in_range():
    dataset = build_calibration_dataset(
        seed=0,
        df=load_diamonds(),
        neg_sizes=[80, 150],
        neg_trials=8,
    )
    pairs = k_fold_predictions(dataset, k=5, seed=0)
    assert len(pairs) == len(dataset)
    for prob, label in pairs:
        assert 0.0 <= prob <= 1.0
        assert label in (0, 1)
