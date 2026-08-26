"""Freeze and load the calibrated confidence model.

The model is fit once, deterministically, on the full labelled dataset and its
coefficients are frozen into ``coefficients.json`` shipped inside the package.
Inference then needs no training data, no diamonds file, and no fit — just the
four weights, the intercept and the feature scaling.

``build_coefficients`` regenerates that JSON (used by the regression test and the
one-off freezing step); ``load_model`` reads the shipped copy.
"""

from __future__ import annotations

import importlib.resources
import json

from .dataset import LabeledSymptom, build_calibration_dataset
from .features import FEATURE_NAMES
from .model import LogisticModel
from .reliability import (
    _DEFAULT_ITERS,
    _DEFAULT_L2,
    _DEFAULT_LR,
    build_reliability_report,
    k_fold_predictions,
)

COEFFICIENTS_RESOURCE = "coefficients.json"


def fit_frozen_model(
    dataset: list[LabeledSymptom],
    *,
    l2: float = _DEFAULT_L2,
    lr: float = _DEFAULT_LR,
    iters: int = _DEFAULT_ITERS,
) -> LogisticModel:
    """Fit the final model on the whole dataset (same recipe as the CV folds)."""
    X = [s.features.as_list() for s in dataset]
    y = [s.label for s in dataset]
    return LogisticModel.fit(X, y, l2=l2, lr=lr, iters=iters)


def build_coefficients(*, seed: int = 0) -> dict[str, object]:
    """Fit the frozen model and bundle it with its measured out-of-fold calibration."""
    dataset = build_calibration_dataset(seed=seed)
    model = fit_frozen_model(dataset)
    report = build_reliability_report(k_fold_predictions(dataset, k=5, seed=seed))

    data = model.to_dict()
    data["feature_order"] = list(FEATURE_NAMES)
    data["metadata"] = {
        "seed": seed,
        "dataset_size": len(dataset),
        "positives": sum(s.label for s in dataset),
        "kfold_ece": report.ece,
        "kfold_mce": report.mce,
        "kfold_brier": report.brier,
        "kfold_mid_range": report.mid_range_count,
    }
    return data


def _coefficients_path():
    return importlib.resources.files("dvi.calibration").joinpath(COEFFICIENTS_RESOURCE)


def load_model() -> LogisticModel:
    """Load the frozen confidence model shipped with the package."""
    data = json.loads(_coefficients_path().read_text(encoding="utf-8"))
    return LogisticModel.from_dict(data)
