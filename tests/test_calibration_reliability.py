"""Reliability diagram, ECE and Brier — the honesty check on the confidence model."""

from dvi.benchmark.real_data import load_diamonds
from dvi.calibration.dataset import LabeledSymptom, build_calibration_dataset
from dvi.calibration.features import FeatureVector
from dvi.calibration.reliability import (
    assign_folds,
    assign_stratified_folds,
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


def _labeled(features: list[float], label: int) -> LabeledSymptom:
    fv = FeatureVector(*features)
    return LabeledSymptom(features=fv, label=label, signature="value_substitution")


# 20 rows with the 4 positives clustered at indices 0,5,10,15 -> all in fold 0
# under index%k=5. Strongly separable features so a model that trains on both
# classes scores the positives high.
def _clustered_dataset() -> list[LabeledSymptom]:
    rows: list[LabeledSymptom] = []
    for i in range(20):
        if i % 5 == 0:
            rows.append(_labeled([0.9, 15.0, 4.0], 1))
        else:
            rows.append(_labeled([0.02, 0.2, 1.5], 0))
    return rows


def test_stratified_folds_keep_every_training_complement_mixed():
    labels = [1 if i % 5 == 0 else 0 for i in range(20)]  # 4 positives, 16 negatives
    folds = assign_stratified_folds(labels, 5)
    assert len(folds) == 20
    total_pos = sum(labels)
    total_neg = len(labels) - total_pos
    # No single fold may hold *all* of a class, or that fold's training complement
    # would be single-class. (With only 4 positives and k=5 not every fold can
    # contain a positive; the invariant that matters is on the complement.)
    for f in range(5):
        fold_pos = sum(labels[i] for i in range(20) if folds[i] == f)
        fold_neg = sum(1 for i in range(20) if folds[i] == f and labels[i] == 0)
        assert fold_pos < total_pos  # some positive remains to train on
        assert fold_neg < total_neg  # some negative remains to train on


def test_k_fold_predictions_score_positives_high_despite_clustering():
    # Under naive index%k, holding out fold 0 leaves an all-negative training set,
    # so the held-out true positives are scored ~0 (silent garbage). Stratified
    # folds keep both classes in every training set.
    pairs = k_fold_predictions(_clustered_dataset(), k=5, seed=0)
    positive_preds = [p for p, y in pairs if y == 1]
    assert positive_preds  # they must be scored, not dropped
    assert all(p > 0.5 for p in positive_preds)


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
