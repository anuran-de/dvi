"""Calibration: a measured probability that a fired symptom is a real change.

The detectors decide *whether* a symptom fires (deterministic). This layer adds
*how confident* we are that it is real — a calibrated logistic model whose
probabilities are validated on held-out data with a reliability diagram. No
hand-tuned confidence numbers.
"""

from .features import FEATURE_NAMES, FeatureVector, extract_features
from .loader import load_model
from .model import LogisticModel
from .score import attach_confidence, score_symptom

__all__ = [
    "FEATURE_NAMES",
    "FeatureVector",
    "LogisticModel",
    "attach_confidence",
    "extract_features",
    "load_model",
    "score_symptom",
]
