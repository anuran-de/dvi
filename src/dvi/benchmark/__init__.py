"""Benchmark: synthetic data and controlled failure injection with ground truth."""

from .evaluate import (
    BenchmarkReport,
    OperatingPoint,
    RcaCaseResult,
    RcaReport,
    ScenarioResult,
    evaluate,
    evaluate_rca,
    recall_at_fixed_fp,
    sweep,
)
from .rca_cases import RcaCase, build_rca_cases
from .scenarios import Scenario, build_scenarios
from .synthetic import (
    categorical,
    inject_value_substitution,
    make_orders,
    numeric,
    ramp,
)

__all__ = [
    "BenchmarkReport",
    "OperatingPoint",
    "RcaCase",
    "RcaCaseResult",
    "RcaReport",
    "Scenario",
    "ScenarioResult",
    "build_rca_cases",
    "build_scenarios",
    "categorical",
    "evaluate",
    "evaluate_rca",
    "inject_value_substitution",
    "make_orders",
    "numeric",
    "ramp",
    "recall_at_fixed_fp",
    "sweep",
]
