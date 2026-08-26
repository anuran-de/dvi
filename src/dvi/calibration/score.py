"""Score a fired symptom with the calibrated confidence model.

This is the inference edge of the calibration layer: turn a symptom plus the two
column profiles it fired on into a measured probability, and optionally return a
copy of the symptom with that probability attached.
"""

from __future__ import annotations

from ..detection.symptom import Symptom
from ..profiling import ColumnProfile
from .features import extract_features
from .model import LogisticModel


def score_symptom(
    symptom: Symptom, baseline: ColumnProfile, current: ColumnProfile, model: LogisticModel
) -> float:
    """Measured P(real change) for a fired symptom, in [0, 1]."""
    features = extract_features(symptom, baseline, current)
    return model.predict_proba([features.as_list()])[0]


def attach_confidence(
    symptom: Symptom, baseline: ColumnProfile, current: ColumnProfile, model: LogisticModel
) -> Symptom:
    """Return a copy of ``symptom`` with ``confidence`` set (original untouched)."""
    confidence = score_symptom(symptom, baseline, current, model)
    return symptom.model_copy(update={"confidence": confidence})
