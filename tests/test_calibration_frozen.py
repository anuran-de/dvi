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


def test_holdout_calibration_stays_within_bounds():
    dataset = build_calibration_dataset(seed=0)
    report = build_reliability_report(k_fold_predictions(dataset, k=5, seed=0))
    # Generous ceilings above the measured ECE≈0.045 / Brier≈0.005; a regression
    # that de-calibrates the model breaks these.
    assert report.ece <= 0.15
    assert report.brier <= 0.05


def test_model_scores_strong_change_above_borderline():
    model = load_model()
    strong = model.predict_proba([[0.5, 15.0, 1.0, 3.5]])[0]
    weak = model.predict_proba([[0.02, 0.5, 1.0, 2.0]])[0]
    assert strong > 0.8
    assert weak < 0.3
    assert strong > weak
