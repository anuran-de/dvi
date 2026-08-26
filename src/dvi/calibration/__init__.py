"""Calibration: a measured probability that a fired symptom is a real change.

The detectors decide *whether* a symptom fires (deterministic). This layer adds
*how confident* we are that it is real — a calibrated logistic model whose
probabilities are validated on held-out data with a reliability diagram. No
hand-tuned confidence numbers.
"""

from .model import LogisticModel

__all__ = ["LogisticModel"]
