"""The frozen model must match a fresh re-fit and stay calibrated on held-out data."""

import json

from dvi.calibration.dataset import build_calibration_dataset
from dvi.calibration.features import FEATURE_NAMES
from dvi.calibration.loader import (
    _coefficients_path,
    build_coefficients,
    fit_frozen_model,
    load_model,
)
from dvi.calibration.reliability import build_reliability_report, k_fold_predictions


def test_frozen_coefficients_match_a_fresh_refit():
    frozen = load_model()
    refit = fit_frozen_model(build_calibration_dataset(seed=0))

    assert len(frozen.weights) == len(refit.weights)
    for a, b in zip(frozen.weights, refit.weights, strict=True):
        assert abs(a - b) < 1e-6
    assert abs(frozen.intercept - refit.intercept) < 1e-6


def test_frozen_json_declares_the_feature_order():
    data = json.loads(_coefficients_path().read_text(encoding="utf-8"))
    assert data["feature_order"] == FEATURE_NAMES


def test_frozen_metadata_matches_a_rebuild():
    on_disk = json.loads(_coefficients_path().read_text(encoding="utf-8"))
    rebuilt = build_coefficients(seed=0)
    assert on_disk["metadata"]["dataset_size"] == rebuilt["metadata"]["dataset_size"]
    assert abs(on_disk["metadata"]["kfold_ece"] - rebuilt["metadata"]["kfold_ece"]) < 1e-6


def test_holdout_ranking_quality_stays_within_bounds():
    dataset = build_calibration_dataset(seed=0)
    report = build_reliability_report(k_fold_predictions(dataset, k=5, seed=0))
    # Count-weighted ECE and Brier certify that the model *ranks* obvious real
    # changes above obvious noise; a regression that de-separates them breaks these.
    assert report.ece <= 0.15
    assert report.brier <= 0.05


def test_intermediate_probabilities_are_not_claimed_as_calibrated():
    # Honesty guard: this is a near-separable set, so almost all predictions sit in
    # the extreme bins and the intermediate [0.2, 0.8] band is under-populated. The
    # worst single-bin gap (MCE) is therefore several times the ECE. We assert the
    # regime rather than pretend mid-range confidences are calibration-tested, so
    # nobody reads the low ECE as "0.5 means 50%".
    dataset = build_calibration_dataset(seed=0)
    report = build_reliability_report(k_fold_predictions(dataset, k=5, seed=0))
    assert report.mce >= report.ece  # worst bin is at least the weighted average
    assert report.mce <= 0.35  # measured ≈0.21; a loose ceiling, not a calibration claim
    # The middle is sparse by construction; guard against silently over-claiming it.
    assert report.mid_range_count <= 0.1 * report.count


def test_model_scores_strong_change_above_borderline():
    model = load_model()
    strong = model.predict_proba([[0.5, 15.0, 1.0, 3.5]])[0]
    weak = model.predict_proba([[0.02, 0.5, 1.0, 2.0]])[0]
    assert strong > 0.8
    assert weak < 0.3
    assert strong > weak
